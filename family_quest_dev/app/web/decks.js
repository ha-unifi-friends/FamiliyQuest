// ---------------------------------------------------------------- own flash card decks («Meine Kartei»)
// Everybody keeps own decks, adds own cards or cards from the packs (button in the lesson feedback / per unit)
// and repeats them with the Leitner boxes. Status: new · due (should be known by now) · learning · known.

const DECK_STATUS = () => ({
  known: { icon: "✅", label: T("Known"), color: "var(--good)" },
  learning: { icon: "📈", label: T("Learning"), color: "var(--accent)" },
  due: { icon: "🔁", label: T("Due – should be known by now"), color: "var(--warn, #f59f00)" },
  new: { icon: "🌱", label: T("New"), color: "var(--muted)" },
});

/** Decks made from a pack are named after its subject (English source text) – shown in the own language. */
const deckName = d => d.subject ? I18N.tr(d.name) : d.name;

function deckBar(d) {
  const total = Math.max(1, d.count);
  const st = DECK_STATUS();
  return h("div.deck-bar", ...["known", "learning", "due", "new"].map(k => d[k] ? h("i", { title: st[k].label + ": " + d[k],
    style: { width: (100 * d[k] / total) + "%", background: st[k].color } }) : null));
}

function deckLegend(d) {
  const st = DECK_STATUS();
  return h("div.deck-legend.small", ...["known", "learning", "due", "new"].map(k => h("span", st[k].icon, " ", st[k].label, ": ", h("b", String(d[k] || 0)))));
}

/** Home card: due cards over all decks. */
function deckHomeCard() {
  const sec = h("section.card.deck-home");
  api("me/decks").then(d => {
    sec.replaceChildren(h("div.row", h("h2.grow", "📇 ", T("My card box")),
      h("button.btn" + (d.due ? "" : ".ghost"), { onclick: () => go("deck") }, d.due ? T("Repeat {0} cards").replace("{0}", d.due) : T("Open"))),
      h("p.small.muted", d.decks.length ? d.decks.map(x => x.icon + " " + deckName(x)).join(" · ")
        : T("Your own flash cards – make your own or add words from the lessons with 📇.")));
  }).catch(() => sec.remove());
  return sec;
}

async function decksView() {
  let d;
  try { d = await api("me/decks"); } catch (e) { toast(e.message, "bad"); return go(""); }
  screen("deck", { back: () => go(""), actions: h("button.btn", { onclick: () => deckDialog(null, id => go("deck/" + id)) }, "+ ", T("New deck")) },
    h("h1.deck-top", "📇 ", T("My card box")),
    d.decks.length ? null : h("section.card", h("p", T("Your own flash cards – make your own or add words from the lessons with 📇.")),
      h("p.small.muted", T("In a lesson tap «📇 To my card box» after an answer, or in a pack «📇» next to a unit."))),
    ...d.decks.map(x => h("button.card.deck-tile", { onclick: () => go("deck/" + x.id) },
      h("div.row", h("span.deck-ic", x.icon), h("div.grow", C(deckName(x), "strong"), h("div.small.muted", I18N.tr(T("{0} flash cards")).replace("{0}", x.count))),
        x.due ? h("span.due", "🔁 " + x.due) : null),
      deckBar(x))));
}

function deckDialog(deck, done) {
  const name = h("input", { type: "text", maxlength: 60, value: deck ? deckName(deck) : "", placeholder: I18N.tr(T("e.g. French words")) });
  const icons = ["📇", "🇫🇷", "🇬🇧", "🇮🇹", "🇪🇸", "🇩🇪", "🗺️", "🧠", "🔬", "📖", "➗", "🎵"];
  let icon = deck ? deck.icon : "📇";
  const pick = h("div.row.wrap.deck-icons");
  const drawIcons = () => pick.replaceChildren(...icons.map(i => h("button.icon-btn" + (i === icon ? ".on" : ""), { type: "button", onclick: () => { icon = i; drawIcons(); } }, i)));
  drawIcons();
  const m = modal(h("div.form", h("h2", deck ? T("Edit deck") : T("New deck")),
    h("label.field", T("Name"), name), pick,
    h("div.row", h("button.btn", { onclick: async () => {
      if (!name.value.trim()) return name.focus();
      try {
        const body = { name: name.value, icon };
        const r = deck ? await api(`me/decks/${deck.id}`, { method: "PUT", body }) : await api("me/decks", { method: "POST", body });
        m.close(); done(deck ? deck.id : r.id);
      } catch (e) { toast(e.message, "bad"); }
    } }, T("Save")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  name.focus();
}

function cardDialog(deckId, card, done) {
  const front = h("textarea", { rows: 2, maxlength: 300, placeholder: I18N.tr(T("e.g. the house")) }, card ? card.front : "");
  const back = h("textarea", { rows: 2, maxlength: 300, placeholder: I18N.tr(T("e.g. la maison")) }, card ? card.back : "");
  const save = async more => {
    if (!front.value.trim()) return front.focus();
    if (!back.value.trim()) return back.focus();
    try {
      const body = { front: front.value, back: back.value };
      if (card) await api(`me/decks/cards/${card.id}`, { method: "PUT", body });
      else await api(`me/decks/${deckId}/cards`, { method: "POST", body });
      if (more) { front.value = back.value = ""; front.focus(); toast(T("Card saved"), "good"); done(false); }
      else { m.close(); done(true); }
    } catch (e) { toast(e.message, "bad"); }
  };
  const m = modal(h("div.form", h("h2", card ? T("Edit card") : T("New card")),
    h("label.field", T("Front (question)"), front), h("label.field", T("Back (answer)"), back),
    h("div.row.wrap", h("button.btn", { onclick: () => save(false) }, T("Save")),
      card ? null : h("button.btn.ghost", { onclick: () => save(true) }, "+ ", T("Save and next")),
      card ? h("button.btn.ghost.bad", { onclick: async () => {
        if (!confirm(I18N.tr(T("Delete this card?")))) return;
        try { await api(`me/decks/cards/${card.id}`, { method: "DELETE" }); m.close(); done(true); } catch (e) { toast(e.message, "bad"); } } }, "🗑️ ", T("Delete")) : null,
      h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))), { onClose: () => done(true) });
  front.focus();
}

function cardFace(c, side) {
  const img = side === "front" && c.image ? h("img.deck-img", { src: c.image, alt: "" }) : null;
  const emo = side === "front" && c.emoji ? h("span.deck-emoji", c.emoji) : null;
  return [img, emo, C(side === "front" ? c.front : c.back, "span.deck-text")];
}

async function deckView(id) {
  let d;
  try { d = await api("me/decks/" + id); } catch (e) { toast(e.message, "bad"); return go("deck"); }
  const st = DECK_STATUS();
  const counts = { known: 0, learning: 0, due: 0, new: 0, count: d.cards.length };
  d.cards.forEach(c => counts[c.status]++);
  let filter = "";
  const list = h("div.deck-cards");
  const drawList = () => list.replaceChildren(...d.cards.filter(c => !filter || c.status === filter).map(c =>
    h("button.deck-row", { onclick: () => cardDialog(id, c, changed => changed && deckView(id)), title: st[c.status].label },
      h("span.deck-st", st[c.status].icon), h("span.grow", c.emoji ? c.emoji + " " : "", c.image && !c.front ? "🖼️" : C(c.front)),
      h("span.muted", C(c.back)))));
  drawList();
  const chips = h("div.row.wrap.deck-filter", ...[["", T("All") + " " + counts.count], ...["due", "new", "learning", "known"].map(k => [k, st[k].icon + " " + counts[k]])]
    .map(([k, label]) => h("button.chip" + (filter === k ? ".on" : ""), { onclick: e => { filter = k; chips.querySelectorAll(".chip").forEach(b => b.classList.toggle("on", b === e.currentTarget)); drawList(); } }, label)));
  const toLearn = counts.due + Math.min(15, counts.new);
  screen("deck", { back: () => go("deck"), actions: [
        h("button.icon-btn", { title: T("Edit deck"), onclick: () => deckDialog(d.deck, () => deckView(id)) }, "✏️"),
        h("button.icon-btn", { title: T("Delete deck"), onclick: async () => {
          if (!confirm(I18N.tr(T("Delete the deck «{0}» with all its cards?")).replace("{0}", deckName(d.deck)))) return;
          try { await api("me/decks/" + id, { method: "DELETE" }); go("deck"); } catch (e) { toast(e.message, "bad"); } } }, "🗑️")] },
    h("h1.deck-top", d.deck.icon, " ", C(deckName(d.deck))),
    h("section.card", deckBar(counts), deckLegend(counts),
      h("div.row.wrap.deck-actions",
        h("button.btn.big", { disabled: !toLearn, onclick: () => studyView(id, d.deck, "due") }, "▶ ",
          toLearn ? T("Repeat {0} cards").replace("{0}", toLearn) : T("Nothing due today 🎉")),
        h("button.btn.ghost", { disabled: !counts.count, onclick: () => studyView(id, d.deck, "all") }, "🔀 ", T("Practise all")))),
    h("section.card",
      h("div.sec-head", h("h2", T("Cards")), h("div.head-actions", h("button.btn", { onclick: () => cardDialog(id, null, changed => changed && deckView(id)) }, "+ ", T("New card")))),
      counts.count ? chips : h("p.muted", T("No cards yet.")), list));
}

async function studyView(id, deck, mode) {
  let cards;
  try { cards = (await api(`me/decks/${id}/study?mode=${mode}`)).cards; } catch (e) { return toast(e.message, "bad"); }
  if (!cards.length) return toast(T("Nothing due today 🎉"), "good");
  let i = 0, flipped = false, reverse = false;
  const res = { correct: 0, almost: 0, wrong: 0 };
  const draw = () => {
    if (i >= cards.length) return done();
    const c = cards[i];
    const front = reverse && (c.front || !c.image) ? "back" : "front";
    const back = front === "front" ? "back" : "front";
    const grade = async r => {
      try { await api(`me/decks/cards/${c.id}/grade`, { method: "POST", body: { result: r } }); } catch (e) { return toast(e.message, "bad"); }
      res[r]++; Sound.play(r === "wrong" ? "wrong" : "right"); i++; flipped = false; draw();
    };
    app.replaceChildren(h("div.lesson.deck-study",
      h("div.lesson-top",
        h("button.icon-btn", { "aria-label": T("Stop"), title: T("Stop"), onclick: () => deckView(id) }, "✕"),
        h("div.bar.grow.lesson-progress", h("i", { style: { width: (100 * i / cards.length) + "%" } })),
        h("span.small.muted", (i + 1) + " / " + cards.length),
        h("button.icon-btn", { title: T("Swap sides"), onclick: () => { reverse = !reverse; flipped = false; draw(); } }, "⇄")),
      h("div.lesson-body",
        h("p.small.muted.center", deck.icon, " ", C(deckName(deck))),
        h("button.deck-flash" + (flipped ? ".flipped" : ""), { onclick: () => { flipped = !flipped; draw(); } },
          h("div.deck-face", ...cardFace(c, front)),
          flipped ? h("div.deck-face.back", ...cardFace(c, back)) : h("div.small.muted", T("Tap to flip"))),
        flipped ? h("div.deck-grade",
          h("button.btn.bad", { onclick: () => grade("wrong") }, "❌ ", T("Didn't know")),
          h("button.btn.ghost", { onclick: () => grade("almost") }, "🤏 ", T("Almost")),
          h("button.btn.good", { onclick: () => grade("correct") }, "✅ ", T("Knew it")))
          : h("div.deck-grade", h("button.btn.big", { onclick: () => { flipped = true; draw(); } }, "🔄 ", T("Flip"))))));
  };
  const done = () => app.replaceChildren(h("div.lesson.deck-study", h("div.lesson-body.center",
    h("h1", res.wrong ? "💪" : "🎉"), h("h2", T("Round done")),
    h("p", "✅ " + res.correct + " · 🤏 " + res.almost + " · ❌ " + res.wrong),
    h("p.small.muted", T("What you knew comes back later, the rest again soon.")),
    h("div.row.center", h("button.btn", { onclick: () => deckView(id) }, T("Back to the deck")),
      h("button.btn.ghost", { onclick: () => studyView(id, deck, mode) }, "🔁 ", T("Once more"))))));
  draw();
}

/** «📇» – the cards of an answered lesson step (or a whole unit) into the own deck of that subject. */
async function addToDeck(body, btn) {
  try {
    const r = await api(body.unit ? "me/decks/from-unit" : "me/decks/from-session", { method: "POST", body });
    if (btn) { btn.disabled = true; btn.textContent = "✓ " + r.deck.icon + " " + deckName(r.deck); }
    toast(r.added ? I18N.tr(T("Added to «{1}»: {0}")).replace("{0}", r.added === 1 ? I18N.tr(T("1 flash card")) : I18N.tr(T("{0} flash cards")).replace("{0}", r.added)).replace("{1}", deckName(r.deck))
      : I18N.tr(T("Already in «{0}»")).replace("{0}", deckName(r.deck)), "good");
  } catch (e) { toast(e.message, "bad"); }
}
