// «Wer bin ich?» – live guessing game for the family: everybody on their own device, guests via QR code (familyquest/whoami.py).
// werbinichLive(box, me, back) runs the family table, werbinichStartDialog(onStarted) chooses the category.
// You see the characters of all the others – never your own. Ask yes/no questions, guess or give up; it goes round.
"use strict";

const WB_ICON = "🎭";
const wbName = () => I18N.tr(T("Who am I?"));
const wbCoins = list => list.join(" / ") + " 🪙";
// the category titles in the language of the app (the characters themselves are content and stay as they are)
const WB_CATS = { tiere: T("Animals"), berufe: T("Jobs"), essen: T("Food & fruit"), laender: T("Countries"), schweiz: T("Swiss places & mountains"),
  maerchen: T("Fairy tales & legends"), gegenstaende: T("Things at home"), sport: T("Sports"), personen: T("Famous people") };
const wbCat = c => c ? (WB_CATS[c.key] ? I18N.tr(WB_CATS[c.key]) : c.title) : "";
const WB_VOTE = { yes: "✅", no: "❌", unknown: "🤷" };

function werbinichRulesView(rewards) {
  const items = [T("Everybody gets a character of the category – you see the characters of the others, but not your own."),
    T("On your turn ask a yes/no question (type it or say it aloud). The others answer yes, no or don't know."),
    T("Most say yes? Ask again. Otherwise it is the next player's turn."),
    T("Think you know? Guess «I am …». Right: you are finished and get the next place. Wrong: the next player goes."),
    T("Stuck? Give up to see your character – you are finished without a place."),
    rewards ? I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", wbCoins(rewards)) : null,
    T("Coins only at a table with at least two people of the family – not for guests.")].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

async function werbinichStartDialog(onStarted) {
  let r = {};
  try { r = await api("community/werbinich/rules"); } catch {}
  const cats = r.categories || [];
  let cat = cats.some(c => c.key === r.category) ? r.category : (cats[0] || {}).key;
  const grid = h("div.wb-cats");
  const drawCats = () => grid.replaceChildren(...cats.map(c => h("button.wb-cat" + (c.key === cat ? ".on" : ""),
    { type: "button", "aria-pressed": String(c.key === cat), onclick: () => { cat = c.key; drawCats(); } },
    h("span.wb-cat-ic", c.emoji), h("span", wbCat(c)))));
  drawCats();
  const rw = r.rewards || [0, 0, 0];
  const coins = rw.some(x => x > 0) ? h("p.small.pj-coins", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", wbCoins(rw)), h("br"),
    h("span.muted", T("Coins only at a table with at least two people of the family – not for guests."))) : null;
  const m = modal(h("div.form", h("h2", WB_ICON, " ", wbName()),
    h("p.small.muted", T("Everybody gets a secret character – find out who you are with yes/no questions. At least two players, everybody on their own device.")),
    h("div.field", h("b", T("Category")), grid),
    coins,
    h("div.row", h("button.btn.big", { onclick: async () => {
      try { await api("community/werbinich/start", { method: "POST", body: { category: cat } }); m.close(); onStarted(); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
}

function werbinichLive(box, me, back) {
  let st = null, timer = null, alive = true, lastSig = "", cheered = false, busy = false, lastEvent, lastQ;
  const myId = String(me.id);
  box.classList.add("wb-live");
  // the text fields stay the same elements – a new state from the server does not wipe what you are typing
  const qInput = h("input.wb-input", { type: "text", maxlength: 140, enterkeyhint: "send", placeholder: I18N.tr(T("Your question (or say it aloud)")) });
  const gInput = h("input.wb-input", { type: "text", maxlength: 140, enterkeyhint: "go", placeholder: I18N.tr(T("I am …")) });
  qInput.addEventListener("keydown", e => { if (e.key === "Enter") ask(); });
  gInput.addEventListener("keydown", e => { if (e.key === "Enter") guess(); });
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => {
    const focus = document.activeElement;
    box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
    if ((focus === qInput || focus === gInput) && focus.isConnected) focus.focus();
  };
  const stop = () => { alive = false; clearTimeout(timer); box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open"); };
  window.addEventListener("hashchange", stop, { once: true });
  const act = async (path, body) => {
    if (busy) return false;
    busy = true;
    try { st = await api("community/werbinich/" + path, { method: "POST", body }); draw(true); return true; }
    catch (e) { toast(e.message, "bad"); return false; }
    finally { busy = false; }
  };
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try { st = await api("community/werbinich"); draw(); } catch {}
    timer = setTimeout(poll, 1000);
  }
  const player = id => (st.players || []).find(p => p.id === id) || {};
  const who = id => player(id).name || "?";
  const medal = n => ["🥇", "🥈", "🥉"][n - 1] || n + ".";
  const fill = (key, ...xs) => { let s = I18N.tr(key); xs.forEach((x, i) => { s = s.replace("{" + i + "}", x); }); return s; };

  async function ask() {
    if (await act("ask", { text: qInput.value.trim() })) qInput.value = "";
  }
  async function guess() {
    const text = gInput.value.trim();
    if (!text) { gInput.focus(); return toast(I18N.tr(T("Type who you are")), "bad"); }
    if (await act("guess", { text })) gInput.value = "";
  }
  function giveUp() {
    if (confirm(I18N.tr(T("Give up and see who you are?")))) act("giveup");
  }

  // ---------- what just happened: a short reveal, sounds
  function events() {
    const last = st.last;
    if (lastEvent === undefined) { lastEvent = last && last.t; lastQ = st.last_q && st.last_q.n; return; }   // not on the first look
    if (st.last_q && st.last_q.n !== lastQ) {
      lastQ = st.last_q.n;
      if (st.last_q.asker === myId) { try { Sound.play(st.last_q.result === "yes" ? "right" : "wrong"); } catch {} }
    }
    if (!last || last.t === lastEvent) return;
    lastEvent = last.t;
    const mine = last.player === myId;
    if (last.type === "guess" && last.ok) {
      reveal(last.player, last.char, true);
      try { Sound.play(mine ? "done" : "right"); } catch {}
      if (mine) confetti();
    } else if (last.type === "guess") {
      toast(fill(T("{0}: «{1}» – not right"), who(last.player), last.text));
      try { Sound.play("wrong"); } catch {}
    } else if (last.type === "give_up") {
      reveal(last.player, last.char, false);
    }
  }
  function reveal(pid, char, ok) {
    const p = player(pid);
    const el = h("div.wb-reveal", { onclick: () => el.remove() }, h("div.wb-reveal-in",
      avatarSvg(p.avatar || {}, 56), C(p.name || "?", "strong"),
      h("span.muted", ok ? T("found it:") : T("gave up – it was:")),
      C(char || "?", "div.wb-reveal-char"), ok ? h("div.big-ic", "🎉") : h("div.big-ic", "🏳️")));
    document.querySelectorAll(".wb-reveal").forEach(x => x.remove());
    document.body.append(el);                        // outside the box: a new state must not wipe it
    setTimeout(() => el.remove(), 3200);
  }

  function draw(force) {
    if (!alive || !box.isConnected) return;
    if (st && !Array.isArray(st.players)) st = null;

    turnCue("werbinich", st && st.my_turn);
    const sig = JSON.stringify(st);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    if (!st) return show(h("section.card.center", h("div.big-ic", WB_ICON), h("h2", T("No game right now")), h("button.btn", { onclick: back }, T("Back"))));
    events();
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    const q = st.question;
    // ☰: rules, guests (everybody of the family), close question / skip / end for whoever leads, language
    const lead = isHost() && st.status !== "done";
    const menu = gameMenu({ rules: () => werbinichRulesView(st.coins_on ? st.rewards : null),
      invite: !me.guest && st.status !== "done" ? "werbinich" : null,
      actions: [
        { ic: "✔", label: T("Close question"), hidden: !lead || st.phase !== "play" || !q || q.asker === myId || (q.yes + q.no + q.unknown) === 0, onclick: () => act("close") },
        { ic: "⏭", label: T("Skip"), hidden: !lead || st.phase !== "play",
          onclick: () => { if (confirm(I18N.tr(T("Skip {0}?")).replace("{0}", who(st.turn)))) act("skip"); } },
        { ic: "⏹", label: T("End the game"), danger: true, hidden: !lead, confirm: T("End the game?"), onclick: () => act("end") }],
      onLeave: running ? () => { stop(); back(); } : null });
    const head = h("div.quiz-head.dm-head", h("div.row.head-title", menu, h("h1", WB_ICON, " ", wbName())), h("div.row",
      h("span.chip", st.category.emoji, " ", wbCat(st.category))));
    // only the main action stays as a big button – everything else is in ☰
    const host = lead && st.phase === "lobby" ? h("div.row.center.host-bar",
      h("button.btn", { disabled: st.players.length < 2, onclick: async () => {
        try { const r = await beginGame("community/werbinich/begin", st.players); if (r) { st = r; draw(true); } } catch (e) { toast(e.message, "bad"); } } }, "▶ ", T("Start"))) : null;
    if (st.phase !== "lobby") starterBanner(st.starter, "werbinich");
    if (st.phase === "done") return show(head, result());
    if (!st.joined) return show(close, head, h("section.card.center", h("p", T("Play along on this device?")),
      h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join"))), seats(), host);
    if (st.phase === "lobby") return show(close, head, h("section.card.center", h("h2", T("Waiting for the start …")),
      h("p.muted", T("Everybody joins on their own device – at least two players.")), seats(),
      st.coins_on ? h("p.small", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", wbCoins(st.rewards))) : null), host);
    show(close, head, cards(), panel(), myLog(), host);
  }

  // ---------- the characters: the others' big, your own hidden
  function cards() {
    return h("div.wb-cards", ...st.players.map(p => {
      const me_ = p.id === myId;
      const cls = (st.turn === p.id ? ".turn" : "") + (me_ ? ".mine" : "") + (p.status !== "playing" ? ".fin" : "");
      const badge = p.status === "found" ? h("span.wb-badge", medal(p.place)) : p.status === "gave_up" ? h("span.wb-badge", "🏳️")
        : st.question && st.question.asker === p.id ? h("span.wb-badge", "💬") : null;
      return h("div.wb-card" + cls,
        h("div.wb-who", avatarSvg(p.avatar || {}, 22), C(p.name, "strong.wb-name")), badge,
        p.hidden ? h("div.wb-char.wb-hidden", "❓", h("small", T("That is you")))
          : h("div.wb-char", h("span.wb-emo", st.category.emoji), C(p.char || "?", "span.wb-txt")));
    }));
  }

  function counts(x) {
    return h("div.wb-counts", ...["yes", "no", "unknown"].map(v => h("span.wb-count." + v, WB_VOTE[v], " ", String(x[v] || 0))));
  }
  const quote = (x, asker) => x.text ? C("«" + x.text + "»", "span.wb-q") : h("span.muted.wb-q", asker === myId ? T("(your question, said aloud)") : T("(said aloud)"));

  function panel() {
    const q = st.question, mine = player(myId), done = mine.status !== "playing";
    const giveBtn = !done ? h("button.btn.ghost.small.wb-give", { onclick: giveUp }, "🏳️ ", T("Give up")) : null;
    if (q) {
      const answered = q.yes + q.no + q.unknown;
      const head = h("div.wb-asks", q.asker === myId ? h("strong", T("Your question:")) : h("strong", fill(T("Question from {0}:"), who(q.asker))), " ", quote(q, q.asker));
      if (q.asker === myId) return h("section.card.wb-panel", head, counts(q),
        h("p.small.muted", fill(T("{0} of {1} answered"), answered, q.need)),
        h("div.row.center", h("button.btn", { disabled: !answered, onclick: () => act("close") }, "✔ ", T("Close question")), giveBtn));
      return h("section.card.wb-panel", head,
        h("div.wb-votes", ...[["yes", T("Yes")], ["no", T("No")], ["unknown", T("Don't know")]].map(([v, n]) =>
          h("button.btn.wb-vote." + v + (q.mine === v ? ".on" : ""), { onclick: () => act("answer", { vote: v }) }, WB_VOTE[v], " ", n))),
        h("div.row.center.wb-sub", counts(q), h("span.small.muted", fill(T("{0} of {1} answered"), answered, q.need))), giveBtn);
    }
    const lastQ = st.last_q ? h("p.small.wb-lastq", C(who(st.last_q.asker), "b"), ": ", quote(st.last_q, st.last_q.asker), " → ", WB_VOTE[st.last_q.result], " ", counts(st.last_q)) : null;
    if (st.my_turn) return h("section.card.wb-panel.turn",
      h("strong.wb-turn", "🎯 ", T("Your turn!")),
      h("div.wb-line", qInput, h("button.btn", { onclick: ask }, "❓ ", T("Ask question"))),
      h("div.wb-line", gInput, h("button.btn.ghost", { onclick: guess }, "💡 ", T("Guess"))),
      lastQ, giveBtn);
    return h("section.card.wb-panel",
      h("p.wb-wait", done ? T("You are finished – help the others with your answers!") : fill(T("{0} is thinking of a question …"), who(st.turn))),
      lastQ, giveBtn);
  }

  function myLog() {
    const log = st.my_log || [];
    if (!log.length) return null;
    return h("details.wb-log", h("summary.small", fill(T("My questions ({0})"), log.length)),
      h("ul.small", ...log.slice().reverse().map(e => h("li", WB_VOTE[e.result], " ", e.text ? C(e.text) : h("span.muted", T("(said aloud)")),
        h("span.muted", " · ✅" + e.yes + " ❌" + e.no + " 🤷" + e.unknown)))));
  }

  function seats() {
    return h("div.dm-seats", ...st.players.map(p => h("div.dm-seat" + (p.id === myId ? ".dm-me" : ""),
      avatarSvg(p.avatar || {}, 30), C(p.name, "strong.small.dm-name"))));
  }

  function result() {
    const order = st.ranking || st.players.map(p => p.id);
    const ranked = order.map(player);
    const mine = player(myId);
    if (mine.place === 1 && !cheered) { cheered = true; confetti(); try { Sound.play("done"); } catch {} }
    const winners = ranked.filter(p => p.place === 1).map(p => p.name);
    return h("section.card.center.pj-result.wb-result",
      h("h2", "🏆 ", winners.length ? C(winners.join(" & ")) : T("Nobody found their character")),
      h("p.small.muted", st.category.emoji, " ", wbCat(st.category)),
      h("ol.pk-rank", ...ranked.map(p => h("li", h("span.pj-medal", p.place ? medal(p.place) : p.status === "gave_up" ? "🏳️" : "–"), avatarSvg(p.avatar || {}, 30),
        h("span.grow.wb-res", C(p.name, "strong"), h("br"), C(p.char || "?", "span.wb-res-char")),
        h("span.small.muted", fill(T("{0} questions"), p.questions)), p.coins ? h("b.pj-plus", "+" + p.coins + " 🪙") : null))),
      st.coins_on ? null : h("p.small.muted", T("Coins only at a table with at least two people of the family – not for guests.")),
      h("div.row.center", h("button.btn", { onclick: back }, T("Back"))));
  }
  poll();
}

async function werbinichView() {
  const box = h("div.wb-live");
  screen("games", box);
  werbinichLive(box, S.profile, () => go("games"));
}

async function werbinichFamilyCard() {
  const c = S.me && S.me.community, g = c && c.werbinich;
  return h("section.card.quiz-card", h("h2", WB_ICON, " ", wbName()),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("werbinich") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("Who am I? Everybody gets a secret character and finds out with yes/no questions – everybody on their own device.")),
         h("button.btn", { onclick: () => werbinichStartDialog(() => go("werbinich")) }, "👨‍👩‍👧 ", T("Open a family table"))]);
}
