// Card games where you shed your cards: «Tschau Sepp» (Swiss or French cards) and «Kartenkarussell» (own cards).
// cardsLive(box, me, back, kind) runs a table (family or alone against bots), cardsStartDialog(kind, solo, onStarted) sets the rules.
"use strict";

// Swiss suits: Schellen, Schilten, Rosen, Eicheln (German names come from the dictionaries)
const SWISS_SUITS = { schellen: ["🔔", T("Bells")], schilten: ["🛡️", T("Shields")], rosen: ["🌹", T("Roses")], eicheln: ["🌰", T("Acorns")] };
const FRENCH_SUITS = { s: ["♠︎", T("Spades")], h: ["♥︎", T("Hearts")], d: ["♦︎", T("Diamonds")], c: ["♣︎", T("Clubs")] };
const KARUSSELL_COLORS = { violet: ["var(--ans-1)", T("Violet")], pink: ["var(--ans-2)", T("Raspberry")], orange: ["var(--ans-3)", T("Orange")], petrol: ["var(--ans-4)", T("Petrol")] };
const KARUSSELL_SIGNS = { draw2: "+2", skip: "⊘", reverse: "⇄", wish: "✦", draw4: "+4" };
const CARD_BACKS = { classic: T("Classic"), stars: T("Stars"), waves: T("Waves"), checks: T("Checks") };
const CARD_GAMES = { tschau: { icon: "🂡", title: "Tschau Sepp" }, karussell: { icon: "🎠", title: T("Card Carousel") } };

function shedCard(kind, code, opts = {}) {
  if (!code) return h("div.sh-card.back.back-" + (opts.back || "classic") + (opts.small ? ".small" : ""));
  const [suit, rank] = code.split(":");
  const cls = "div.sh-card" + (opts.small ? ".small" : "") + (opts.big ? ".big" : "") + (opts.on ? ".on" : "") + (opts.dim ? ".dim" : "");
  if (kind === "karussell") {
    const wild = suit === "wild";
    return h(cls + ".ka" + (wild ? ".wild" : ""), { style: wild ? {} : { "--kc": KARUSSELL_COLORS[suit][0] }, translate: "no", onclick: opts.onclick,
      title: wild ? (KARUSSELL_SIGNS[rank] || rank) + " · " + I18N.tr(T("wish a colour")) : I18N.tr(KARUSSELL_COLORS[suit][1]) + " " + (KARUSSELL_SIGNS[rank] || rank) },
      h("b", KARUSSELL_SIGNS[rank] || rank));
  }
  const swiss = !!SWISS_SUITS[suit];
  const sign = swiss ? SWISS_SUITS[suit][0] : FRENCH_SUITS[suit][0];
  const red = !swiss && (suit === "h" || suit === "d");
  return h(cls + (red ? ".red" : "") + (swiss ? ".swiss" : ""), { translate: "no", onclick: opts.onclick, title: rank + " " + I18N.tr(swiss ? SWISS_SUITS[suit][1] : FRENCH_SUITS[suit][1]) },
    h("b", rank), h("i", sign));
}

// ---------------------------------------------------------------- pairs: emoji sets, photo sets and card backs (paarjagd.js)
const PAIR_SETS = {
  animals: [T("Animals"), "🐶 🐱 🐭 🐹 🐰 🦊 🐻 🐼 🐨 🐯 🦁 🐮 🐷 🐸 🐵 🐔 🐧 🦉 🦄 🐝"],
  fruit: [T("Fruit and vegetables"), "🍎 🍐 🍊 🍋 🍌 🍉 🍇 🍓 🫐 🍒 🍑 🥭 🍍 🥥 🥝 🍅 🥑 🥕 🌽 🥦"],
  vehicles: [T("Vehicles"), "🚗 🚕 🚌 🚎 🏎️ 🚓 🚑 🚒 🚐 🚚 🚜 🛵 🏍️ 🚲 🛴 🚂 ✈️ 🚀 🚁 ⛵"],
  sea: [T("In the sea"), "🐳 🐬 🐟 🐠 🐡 🦈 🐙 🦑 🦀 🦞 🦐 🐚 🪼 🐢 🦭 🦦 🦩 🦢 ⚓ 🏝️"],
};
// the emoji sets and the family's photo sets (GET community/memory): key → { name, items: [{ emoji } | { img }] }
function pairSets(fam) {
  return { ...Object.fromEntries(Object.entries(PAIR_SETS).map(([k, [n, list]]) => [k, { name: I18N.tr(n), items: list.split(" ").map(e => ({ emoji: e })) }])),
    ...Object.fromEntries(((fam && fam.sets) || []).map(st => ["photo:" + st.id, { name: "📷 " + st.name, items: st.photos.map(u => ({ img: u })) }])) };
}
// the back of a pairs card: a card back (CARD_BACKS) or the family crest
function pairBack(back, crest) {
  return h("div.mm-back.back-" + back, back === "crest" ? crestSvg(crest, { ribbon: false }) : null);
}
// the face of a pairs card
function pairFace(it) {
  return h("div.mm-face", it.img ? h("img", { src: it.img, alt: "" }) : h("span", { translate: "no" }, it.emoji));
}

function suitName(kind, s) {
  if (kind === "karussell") return I18N.tr(KARUSSELL_COLORS[s][1]);
  return I18N.tr(SWISS_SUITS[s] ? SWISS_SUITS[s][1] : FRENCH_SUITS[s][1]);
}

function suitsOf(kind, rules) {
  if (kind === "karussell") return Object.keys(KARUSSELL_COLORS);
  return rules.deck === "french" ? Object.keys(FRENCH_SUITS) : Object.keys(SWISS_SUITS);
}

// own and shared bots of the children: tap to put them at the table (the rest are animal bots)
// bots at the table: own bots of the children, and how fast the bots react (0 = at once)
function botPicker(ms = 1400) {
  const chosen = new Set(), box = h("div.bot-pick");
  const speed = h("select", ...[[0, T("at once")], [500, "0.5 s"], [1000, "1 s"], [1400, "1.4 s"], [2000, "2 s"], [3000, "3 s"], [5000, "5 s"]]
    .map(([v, n]) => h("option", { value: v, selected: v === (ms ?? 1400) }, I18N.tr(n))));
  if (![0, 500, 1000, 1400, 2000, 3000, 5000].includes(ms ?? 1400)) speed.append(h("option", { value: ms, selected: true }, (ms / 1000) + " s"));
  const speedRow = h("label.field.bot-speed", "⏱️ ", T("Reaction time of the bots"), speed);
  api("community/bots").then(d => {
    if (!d.bots.length) return;
    box.replaceChildren(h("b.small", T("Your bots at the table")), h("div.row.wrap", ...d.bots.map(b => h("button.bot-chip", { type: "button",
      onclick: e => { chosen.has(b.id) ? chosen.delete(b.id) : chosen.add(b.id); e.currentTarget.classList.toggle("on", chosen.has(b.id)); } },
      h("span.bot-av", { style: { width: "26px", height: "26px", fontSize: "15px", background: b.color } }, ["degu", "goldfish"].includes(b.kind) && typeof petIcon === "function" ? petIcon(b.kind, 20) : b.emoji), C(b.name)))));
  }).catch(() => {});
  return { el: h("div", speedRow, box), ids: () => [...chosen], ms: () => +speed.value };
}

async function cardsStartDialog(kind, solo, onStarted) {
  let r = {};
  try { r = await api(`community/cards/${kind}/rules`); } catch {}
  const chk = (k, label) => { const i = h("input", { type: "checkbox", checked: !!r[k] }); return [k, i, h("label.check", i, label)]; };
  const sel = (v, list) => h("select", ...list.map(([k, n]) => h("option", { value: k, selected: String(v) === String(k) }, n)));
  const f = {
    hand: sel(r.hand ?? 7, [[5, "5"], [6, "6"], [7, "7"], [8, "8"]]),
    rounds: sel(r.rounds ?? 1, [[1, "1"], [3, "3"], [5, "5"]]),
    bots: sel(r.bots ?? (solo ? 2 : 0), (solo ? [1, 2, 3, 4, 5] : [0, 1, 2, 3, 4]).map(n => [n, String(n)])),
    level: sel(r.level || "normal", [["easy", T("easy")], ["normal", T("normal")]]),
    penalty: sel(r.penalty ?? 2, [[0, T("none")], [1, "1"], [2, "2"], [3, "3"]]),
  };
  if (kind === "tschau") f.deck = sel(r.deck || "swiss", [["swiss", T("Swiss cards (Bells, Shields, Roses, Acorns)")], ["french", T("French cards (♠ ♥ ♦ ♣)")]]);
  const special = kind === "tschau" ? [chk("draw2", T("7: the next one draws 2")), chk("skip", T("8: the next one is skipped")),
    chk("wish", T("Under / Jack: wish a suit")), chk("again", T("Ace: play once more")), chk("reverse", T("10: change the direction")),
    chk("stack", T("Draw cards add up (answer a 7 with a 7)"))] : [chk("stack", T("Draw cards add up (answer +2 with +2)"))];
  const calls = kind === "tschau" ? "«Tschau» / «Sepp»" : "«" + I18N.tr(T("Last card!")) + "» / «" + I18N.tr(T("Done!")) + "»";
  // card back: tap one – the chosen one is marked
  let back = CARD_BACKS[r.back] ? r.back : "classic";
  const backPrev = h("div.row.back-pick");
  const drawBacks = () => backPrev.replaceChildren(...Object.keys(CARD_BACKS).map(b => h("button.back-opt" + (b === back ? ".on" : ""),
    { type: "button", title: I18N.tr(CARD_BACKS[b]), "aria-label": I18N.tr(CARD_BACKS[b]), "aria-pressed": String(b === back), onclick: () => { back = b; drawBacks(); } },
    shedCard(kind, null, { back: b, small: true }), h("span.back-name", CARD_BACKS[b]))));
  drawBacks();
  const picker = botPicker(r.bot_ms);
  const m = modal(h("div.form", h("h2", CARD_GAMES[kind].icon, " ", CARD_GAMES[kind].title, solo ? " – " + I18N.tr(T("alone against bots")) : ""),
    f.deck ? h("label.field", T("Cards"), f.deck) : null,
    h("div.grid3", h("label.field", T("Cards in the hand"), f.hand), h("label.field", T("Rounds"), f.rounds),
      h("label.field", solo ? T("Bots") : T("Bots at the table"), f.bots), h("label.field", T("Bots play"), f.level),
      h("label.field", I18N.tr(T("Penalty cards for a forgotten {0}")).replace("{0}", calls), f.penalty)),
    picker.el,
    h("div.field", h("b", T("Card back")), backPrev),
    h("div.cards-rules", ...special.map(x => x[2])),
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      const body = { solo, hand: +f.hand.value, rounds: +f.rounds.value, bots: Math.max(+f.bots.value, picker.ids().length), level: f.level.value,
        penalty: +f.penalty.value, back, bot_ids: picker.ids(), bot_ms: picker.ms() };
      if (f.deck) body.deck = f.deck.value;
      for (const [k, i] of special) body[k] = i.checked;
      try { await api(`community/cards/${kind}/start`, { method: "POST", body }); m.close(); onStarted(); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", solo ? T("Play") : T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  withoutBots(kind, f.bots, f.level, picker.el);          // parent area › Games: without bots
}

function cardsRulesView(kind, r) {
  const calls = kind === "tschau" ? ["Tschau", "Sepp"] : [I18N.tr(T("Last card!")), I18N.tr(T("Done!"))];
  const items = [T("Play a card with the same suit or the same value as the top card – or draw one."),
    I18N.tr(T("Going down to one card, tap «{0}» before you play; with your last card «{1}». Forgotten: penalty cards.")).replace("{0}", calls[0]).replace("{1}", calls[1]),
    T("Who has no cards first wins the round; the others count the points of their cards. After the last round, the fewest points win.")];
  if (kind === "tschau") {
    if (r.draw2) items.push(T("7: the next one draws 2")); if (r.skip) items.push(T("8: the next one is skipped"));
    if (r.wish) items.push(T("Under / Jack: wish a suit")); if (r.again) items.push(T("Ace: play once more")); if (r.reverse) items.push(T("10: change the direction"));
  } else items.push(T("+2: the next one draws 2 · ⊘: skip · ⇄: change the direction · ✦: wish a colour · +4: wish a colour, the next one draws 4"));
  if (r.stack) items.push(T("Draw cards add up – answer with the same card or take them all."));
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", typeof x === "string" ? I18N.tr(x) : x))));
}

function cardsLive(box, me, back, kind) {
  let st = null, timer = null, alive = true, lastSig = "", say = false;
  const myId = String(me.id);
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => { alive = false; clearTimeout(timer); box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open"); };
  window.addEventListener("hashchange", stop, { once: true });
  const act = async (path, body) => {
    try { st = await api(`community/cards/${kind}/${path}`, { method: "POST", body }); say = false; draw(true); }
    catch (e) { toast(e.message, "bad"); }
  };
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try { st = await api(`community/cards/${kind}`); draw(); } catch {}
    timer = setTimeout(poll, 900);
  }
  const who = id => (st.players.find(p => p.id === id) || {}).name || "?";
  // «Invite guests» (☰ and the button in the lobby box): the game key – null for solo tables, guests, finished games
  function invite() { return !st.solo && !me.guest && st.status !== "done" ? kind : null; }
  function draw(force) {
    if (!alive || !box.isConnected) return;                            // the game was left meanwhile: a late answer
    if (st && !Array.isArray(st.players)) st = null;                 // not a game state (e.g. after «end»): no game
    turnCue("cards", st && st.phase === "play" && st.turn === myId);
    const sig = JSON.stringify(st && [st.phase, st.turn, st.top, st.hand, st.pending, st.wish, st.drawn, st.round, st.players.map(p => [p.cards, p.said]), Math.ceil((st.next_ms || 0) / 1000)]) + say;
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    if (!st) return show(h("section.card.center", h("div.big-ic", CARD_GAMES[kind].icon), h("h2", T("No game right now")), noTableActions(kind, back)));
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    // ☰: rules, guests (everybody of the family at a family table), the actions of whoever leads, language
    const menu = gameMenu({ rules: () => cardsRulesView(kind, st.rules),
      invite: invite(),
      actions: [{ ic: "⏹", label: T("End the game"), danger: true, hidden: !isHost() || st.status === "done", confirm: T("End the game?"),
        onclick: () => act("end").then(() => { stop(); back(); }) }],
      onLeave: running ? () => { stop(); back(); } : null });
    const head = h("div.quiz-head", h("div.row.head-title", menu, h("h1", CARD_GAMES[kind].icon, " ", CARD_GAMES[kind].title)), h("div.row",
      st.round ? h("span.chip", I18N.tr(T("Round {0} of {1}")).replace("{0}", st.round).replace("{1}", st.rules.rounds)) : null));
    // only the main action stays as a big button – everything else is in ☰
    const host = isHost() && st.phase === "lobby" && st.status !== "done" ? h("div.row.center.host-bar",
      h("button.btn", { onclick: async () => { try { const r = await beginGame(`community/cards/${kind}/begin`, st.players); if (r) { st = r; draw(true); } } catch (e) { toast(e.message, "bad"); } } }, "▶ ", T("Deal"))) : null;
    if (st.phase !== "lobby") starterBanner(st.starter, "cards-" + kind);
    if (st.phase === "done") {
      const rank = (st.ranking || []).map(id => st.players.find(p => p.id === id)).filter(Boolean);
      if (rank[0] && rank[0].id === myId) { confetti(); try { Sound.play("done"); } catch {} }
      return show(head, h("section.card.center", h("h2", "🏆 ", C(rank[0] ? rank[0].name : "")),
        h("ol.pk-rank", ...rank.map(p => h("li", seatIcon(p, 32), C(p.name, "strong.grow"), h("span.small.muted", I18N.tr(p.score === 1 ? T("1 point") : T("{0} points")).replace("{0}", p.score))))),
        h("button.btn", { onclick: back }, T("Back"))));
    }
    if (!st.joined) return show(close, head, h("section.card.center", h("p", T("Play along on this device?")),
      h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join"))), seats(), host);
    if (st.phase === "lobby") return show(close, head, h("section.card.center", h("h2", T("Waiting for the start …")),
      h("p.muted", T("Everybody joins on their own device.")), seats(), inviteBtn(invite())), host);
    show(close, head, seats(), middle(), mine(), host);
  }
  function seatIcon(p, size) {
    return p.bot ? h("span.bot-av", { style: { width: size + "px", height: size + "px", fontSize: (size * 0.6) + "px", background: p.color || null } }, p.emoji || "🤖") : avatarSvg(p.avatar || {}, size);
  }
  function seats() {
    return h("div.sh-seats", ...st.players.map(p => h("div.sh-seat" + (st.turn === p.id ? ".turn" : "") + (p.id === myId ? ".me" : ""),
      seatIcon(p, 40), h("div.grow", C(p.name, "strong.small"),
        h("div.sh-count", ...Array.from({ length: Math.min(p.cards, 10) }, () => h("i")), h("span.small", " " + p.cards)),
        p.said != null && p.cards <= 1 ? h("span.pk-tag.allin", p.cards === 1 ? (st.calls[0]) : st.calls[1]) : null,
        st.rules.rounds > 1 ? h("div.small.muted", I18N.tr(p.score === 1 ? T("1 point") : T("{0} points")).replace("{0}", p.score)) : null))));
  }
  function middle() {
    const myTurn = st.turn === myId && st.phase === "play";
    const last = st.last ? (st.last.card ? I18N.tr(T("{0} played")).replace("{0}", who(st.last.player)) + (st.last.penalty ? " · " + I18N.tr(T("forgot to call – {0} penalty cards")).replace("{0}", st.last.penalty) : "")
      : I18N.tr(T("{0} drew {1} cards")).replace("{0}", who(st.last.player)).replace("{1}", st.last.drew)) : "";
    const res = st.phase === "between" && st.round_result ? h("div.pk-result", "🏆 ", I18N.tr(T("{0} won the round")).replace("{0}", who(st.round_result.winner)),
      h("div.small", I18N.tr(T("Next round in {0} s")).replace("{0}", Math.ceil((st.next_ms || 0) / 1000)))) : null;
    return h("div.sh-table",
      h("div.row.center.sh-piles",
        h("button.sh-pile" + (myTurn && !st.drawn ? ".can" : ""), { disabled: !myTurn || st.drawn, onclick: () => act("draw"), title: T("Draw") },
          shedCard(kind, null, { back: st.rules.back }), h("span.small", st.pending ? "+" + st.pending : String(st.deck_left))),
        st.top ? shedCard(kind, st.top, { big: true }) : null,
        h("div.sh-info", st.wish ? h("div", T("wished:"), " ", h("b", suitName(kind, st.wish)), kind === "karussell" ? h("span.sh-dot", { style: { background: KARUSSELL_COLORS[st.wish][0] } }) : " " + (SWISS_SUITS[st.wish] || FRENCH_SUITS[st.wish] || [""])[0]) : null,
          st.pending ? h("div.warn-text", I18N.tr(T("Draw {0} – or answer with the same card")).replace("{0}", st.pending)) : null,
          h("div.small.muted", st.direction === 1 ? "↻" : "↺"))),
      h("div.small.muted.center", last), res);
  }
  function mine() {
    if (!st.hand) return null;
    const myTurn = st.turn === myId && st.phase === "play";
    const playable = new Set(st.playable || []);
    const n = st.hand.length;
    const needCall = myTurn && (n === 2 || n === 1) && playable.size;
    const callBtn = needCall ? h("button.btn" + (say ? ".good" : ".ghost"), { onclick: () => { say = !say; draw(true); } }, "📣 ", n === 2 ? st.calls[0] : st.calls[1]) : null;
    const tap = async c => {
      if (!myTurn || !playable.has(c)) return;
      const [, rank] = c.split(":");
      const wild = (kind === "karussell" && c.startsWith("wild")) || (kind === "tschau" && st.rules.wish && (rank === "U" || rank === "J"));
      if (wild) {
        const m = modal(h("div.form.center", h("h2", T("Which suit do you wish?")), h("div.row.center.wrap",
          ...suitsOf(kind, st.rules).map(s => h("button.btn.big", { style: kind === "karussell" ? { background: KARUSSELL_COLORS[s][0] } : {},
            onclick: () => { m.close(); act("play", { card: c, wish: s, say }); } },
            kind === "karussell" ? "" : (SWISS_SUITS[s] || FRENCH_SUITS[s])[0] + " ", suitName(kind, s))))));
        return;
      }
      act("play", { card: c, say });
    };
    return h("section.card.sh-mine" + (myTurn ? ".turn" : ""),
      h("p.center", myTurn ? h("strong", st.drawn ? T("Play the card you drew – or pass.") : T("Your turn!")) : h("span.small.muted", I18N.tr(T("{0} is playing …")).replace("{0}", who(st.turn)))),
      h("div.sh-hand", ...st.hand.map((c, i) => shedCard(kind, c, { on: myTurn && playable.has(c) && (!st.drawn || i === n - 1), dim: myTurn && !playable.has(c), onclick: () => tap(c) }))),
      h("div.row.center.wrap", callBtn,
        myTurn && st.drawn ? h("button.btn.ghost", { onclick: () => act("pass") }, T("Pass")) : null,
        myTurn && !st.drawn && !playable.size ? h("button.btn", { onclick: () => act("draw") }, st.pending ? I18N.tr(T("Draw {0}")).replace("{0}", st.pending) : T("Draw")) : null));
  }
  poll();
}

async function cardsView(kind) {
  const box = h("div.cards-live");
  screen("games", box);
  cardsLive(box, S.profile, () => go("games"), kind);
}

async function cardsFamilyCard(kind) {
  const c = S.me && S.me.community, g = c && c[kind];
  return h("section.card.quiz-card", h("h2", CARD_GAMES[kind].icon, " ", CARD_GAMES[kind].title),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go(kind) }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", kind === "tschau" ? T("The Swiss card game: shed your cards, say «Tschau» and «Sepp»!") : I18N.tr(T("Shed your cards – colours, numbers and special cards. Say «{0}» in time!")).replace("{0}", I18N.tr(T("Last card!")))),
         gameStartRow(botsOn(kind) ? () => cardsStartDialog(kind, true, () => go(kind)) : null, () => cardsStartDialog(kind, false, () => go(kind)))]);
}
