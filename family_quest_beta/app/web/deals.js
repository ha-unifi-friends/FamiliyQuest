// Deals (familyquest/deals.py): children trade with each other and with their parents – coins, chores, pets, avatar
// items, games, free text. Offer → counter-offer → accept (the same version) → the deal stands → it is executed.
// Used by the children's app (#/deals, #/deals/<id>) and by the parent area (tab «Deals»: own deals, overview, settings).
"use strict";

const DEAL_STATUS = { open: T("Open"), approval: T("Waiting for parents"), running: T("Running"), done: T("Done"),
  rejected: T("Rejected"), withdrawn: T("Withdrawn"), declined: T("Not allowed by parents"), failed: T("Failed"), cancelled: T("Cancelled") };
const DEAL_REASON = { missed: T("A taken-over chore was not done in time"), rejected: T("A parent rejected a taken-over chore"),
  removed: T("A chore of the deal was removed"), gone: T("Something of the deal is no longer there"), text: T("The free deal was not fulfilled"),
  cancelled: T("A parent cancelled the deal"), council: T("The family council decided: not done") };
const DEAL_BASE_AVATAR = { skin: "#f1c27d", hair: "short", hairColor: "#6b3e1f", eyes: "round", mouth: "smile", outfit: "tshirt", outfitColor: "#4f8cff", items: {} };

const dealTr = (s, ...a) => a.reduce((t, x, i) => t.replace("{" + i + "}", x), I18N.tr(s));
const dealCall = (path, opts) => (typeof call === "function" && window.FQ_PARENT_AREA ? call : api)(path, opts);

function dealDay(iso) {
  const t = new Date(); const d = new Date(iso + "T12:00");
  const diff = Math.round((new Date(d.toDateString()) - new Date(t.toDateString())) / 86400000);
  if (diff === 0) return I18N.tr(T("today"));
  if (diff === 1) return I18N.tr(T("tomorrow"));
  return d.toLocaleDateString(I18N.locale, { weekday: "short", day: "numeric", month: "numeric" });
}

// the picture of a thing: pet, avatar item on a small avatar, game icon …
function dealPic(it, size = 34) {
  if (it.t === "pet") return h("span.deal-pic", petIcon(it.kind, size, it.emoji));
  if (it.t === "avatar") {
    const base = (typeof S !== "undefined" && S && S.me && S.me.profile && S.me.profile.avatar) || DEAL_BASE_AVATAR;
    return h("span.deal-pic", avatarSvg({ ...base, items: { [it.slot]: it.item } }, size + 6));
  }
  const ic = { coins: "🪙", chore: it.icon || "🧹", newchore: it.icon || "🧹", game: it.icon || "🎮", text: "✍️" }[it.t] || "🎁";
  return h("span.deal-pic.deal-emoji", { style: { fontSize: Math.round(size * .7) + "px" } }, ic);
}

// one building block as a line: picture, name, details
function dealItem(it, { owner = "", onRemove = null } = {}) {
  let main, sub = null;
  if (it.t === "coins") main = h("b", fmt(it.n) + " ", T("coins"));
  else if (it.t === "text") main = C("«" + it.text + "»", "span.deal-text");
  else if (it.t === "chore") {
    main = h("span", C(it.name, "b"), it.times > 1 ? " × " + it.times : "");
    sub = h("span.small.muted", (it.dates || []).map(dealDay).join(", "),
      it.points && it.account !== "xp" ? " · " + I18N.tr(it.to === "owner" ? T("chore coins to {0}") : T("chore coins to who does it")).replace("{0}", owner || "?") + " (" + fmt(it.points) + ")" : "");
  } else if (it.t === "newchore") {
    main = h("span", C(it.name, "b"));
    sub = h("span.small.muted", T("new task"), " · ", dealDay(it.date));
  } else if (it.t === "pet") main = h("span", C(it.name, "b"), " ", h("span.small.muted", T("pet")));
  else if (it.t === "avatar") main = h("span", h("b", it.name), " ", h("span.small.muted", T("avatar item")));
  else if (it.t === "game") main = h("span", h("b", it.name), " ", h("span.small.muted", T("game")));
  return h("div.deal-item.deal-t-" + it.t, dealPic(it, 30), h("div.deal-item-txt", main, sub),
    onRemove ? h("button.icon-btn.deal-rm", { "aria-label": T("Remove"), title: T("Remove"), onclick: onRemove }, "✕") : null);
}

function dealSides(give, get, who) {
  const col = (title, items, owner) => h("div.deal-side", h("div.deal-side-h", title),
    items.length ? items.map(it => dealItem(it, { owner })) : h("p.small.muted", "–"));
  return h("div.deal-sides", col(who.giveTitle, give, who.otherName), col(who.getTitle, get, who.meName));
}

function dealStatusChip(v) {
  const txt = v.status === "open" ? (v.turn ? T("Your answer") : dealTr(T("waiting for {0}"), v.with.name)) : DEAL_STATUS[v.status] || v.status;
  return h("span.deal-chip.st-" + v.status + (v.turn ? ".turn" : ""), txt);
}

// a deal in a list
function dealCard(v, onOpen) {
  const short = items => items.map(it => it.t === "coins" ? "🪙 " + it.n : it.t === "text" ? "✍️" : it.t === "chore" ? (it.icon || "🧹") + (it.times > 1 ? "×" + it.times : "")
    : it.t === "pet" ? (it.emoji || "🐾") : it.t === "game" ? (it.icon || "🎮") : it.t === "newchore" ? (it.icon || "🧹") : "🎁").join(" ");
  const p = v.progress || {};
  const units = ((p.give || {}).units || 0) + ((p.get || {}).units || 0), done = ((p.give || {}).done || 0) + ((p.get || {}).done || 0);
  return h("button.deal-card.card" + (v.new ? ".new" : ""), { onclick: () => onOpen(v) },
    avatarSvg(v.with.avatar, 44),
    h("div.grow.deal-card-mid",
      h("div.row.deal-card-top", C(v.with.name, "strong"), dealStatusChip(v)),
      h("div.small.deal-card-sum", h("span.muted", T("You give"), ": "), short(v.give), h("span.muted", "  ·  ", T("you get"), ": "), short(v.get)),
      v.status === "running" && units ? h("div.deal-bar", bar(done, units, "var(--good)")) : null),
    v.new ? h("span.deal-dot", { "aria-label": T("new") }) : null);
}

// ---------------------------------------------------------------- the thread: current terms, progress, actions, history
function dealThreadEl(v, { refresh, parent = false } = {}) {
  const who = { giveTitle: parent ? dealTr(T("What {0} gives"), v.a.name) : I18N.tr(T("I give")),
    getTitle: parent ? dealTr(T("What {0} gives"), v.b.name) : I18N.tr(T("I get")), meName: v.me.name, otherName: v.with.name };
  const act = async (path, body, okMsg) => {
    try { const r = await dealCall((parent ? "parent/deals/" : "me/deals/") + v.id + "/" + path, { method: "POST", body: body || {} });
      if (okMsg) toast(okMsg, "good"); refresh(r); } catch (e) { if (!parent) toast(e.message, "bad"); }
  };
  const c = v.can || {};
  const p = v.progress || {};
  const head = h("div.deal-head", avatarSvg(parent ? v.a.avatar : v.me.avatar, 40), h("span.deal-swap", "⇄"), avatarSvg(parent ? v.b.avatar : v.with.avatar, 40),
    h("div.grow", C(parent ? v.a.name + " ⇄ " + v.b.name : v.with.name, "strong"), h("div", dealStatusChip(v), " ",
      h("span.small.muted", dealTr(T("Version {0}"), v.version)))));
  const banner = v.status === "running" ? h("div.deal-banner.good", "🤝 ", T("The deal stands!"))
    : v.status === "done" ? h("div.deal-banner.good", "🎉 ", T("Deal done – everything is transferred."))
    : v.status === "approval" ? h("div.deal-banner", "⏳ ", T("Both agreed – a parent has to allow this deal first."))
    : ["failed", "cancelled"].includes(v.status) ? h("div.deal-banner.bad", "❌ ", DEAL_REASON[v.reason] || T("The deal failed"), " – ", T("reservations released, chores back to their owner."))
    : null;
  const units = side => (side && side.chores || []).map(t => h("div.deal-unit.st-" + t.status, h("span", t.status === "done" ? "✅" : t.status === "pending" ? "⏳" : t.status === "open" ? "○" : "✕"),
    h("span", t.icon, " "), C(t.name, "span.grow"), h("span.small.muted", t.weekly ? T("this week") : t.period ? dealDay(t.period) : "")));
  const prog = v.status === "running" || v.status === "done" ? h("div.deal-prog",
    ...(units(p.give).length ? [h("div.small.muted", parent ? v.a.name : I18N.tr(T("Chores I do")))].concat(units(p.give)) : []),
    ...(units(p.get).length ? [h("div.small.muted", parent ? v.b.name : I18N.tr(T("Chores done for me")))].concat(units(p.get)) : []),
    (p.give && p.give.text) || (p.get && p.get.text) ? h("div.small", "✍️ ", T("Free deal:"), " ",
      p.give && p.give.text_done || p.get && p.get.text_done ? h("b", T("done ✓")) : [
        p.text.me ? h("span", parent ? v.a.name : I18N.tr(T("You")), " ✓ ") : null, p.text.other ? h("span", parent ? v.b.name : v.with.name, " ✓ ") : null,
        p.dispute ? h("b.bad-text", T("not agreed")) : null]) : null) : null;
  const actions = h("div.row.deal-actions",
    c.accept ? h("button.btn.good", { onclick: () => act("accept", { version: v.version }, T("Accepted")) }, "✓ ", T("Accept")) : null,
    c.counter ? h("button.btn.ghost", { onclick: () => dealBuilder({ deal: v, after: refresh }) }, "↔ ", T("Counter-offer")) : null,
    c.reject ? h("button.btn.ghost.deal-no", { onclick: () => confirm(I18N.tr(T("Reject this offer?"))) && act("reject", { text: "" }) }, "✕ ", T("Reject")) : null,
    c.withdraw ? h("button.btn.ghost", { onclick: () => confirm(I18N.tr(T("Withdraw your offer?"))) && act("withdraw") }, T("Withdraw")) : null,
    c.confirm && !(p.text && p.text.me) ? h("button.btn.good", { onclick: () => act("confirm", { ok: true }) }, T("Done ✓")) : null,
    c.confirm ? h("button.btn.ghost", { onclick: () => confirm(I18N.tr(T("Say that the free deal was not done? A parent decides then."))) && act("confirm", { ok: false }) }, "✗ ", T("Not done")) : null,
    c.council ? h("button.btn.ghost", { onclick: () => act("council", { lang: I18N.lang || "" }, T("Sent to the family council")) }, "🏛️ ", T("To the family council")) : null,
    parent && v.status === "approval" ? [h("button.btn.good", { onclick: () => act("approve", { ok: true }) }, "✓ ", T("Allow")),
      h("button.btn.ghost", { onclick: () => act("approve", { ok: false }) }, "✕ ", T("Do not allow"))] : null,
    parent && v.status === "running" && p.dispute ? [h("button.btn.good", { onclick: () => act("settle", { ok: true }) }, T("Decide: done")),
      h("button.btn.ghost", { onclick: () => act("settle", { ok: false }) }, T("Decide: not done"))] : null,
    parent && ["open", "approval", "running"].includes(v.status) ? h("button.btn.small.bad", {
      onclick: () => confirm(I18N.tr(T("Cancel this deal? Reservations are released, chores go back."))) && act("cancel") }, T("Cancel deal")) : null);
  return h("div.deal-thread", head, banner, dealSides(v.give, v.get, who), prog, actions,
    h("h3.deal-hist-h", "💬 ", T("History")), h("div.deal-msgs", ...(v.messages || []).map(m => dealMsg(m, v, parent))));
}

function dealMsg(m, v, parent) {
  const d = m.data || {};
  const name = m.name || "";
  const nameOf = id => id === v.me.id ? v.me.name : id === v.with.id ? v.with.name : "?";
  const sys = (ic, txt) => h("div.deal-msg.sys", h("span", ic, " "), txt, h("span.deal-at", fmtTime(m.at)));
  const bubble = (...content) => h("div.deal-msg" + (m.mine ? ".mine" : ".theirs"), m.mine ? null : C(name, "div.deal-who"), ...content,
    h("span.deal-at", fmtDateTime(m.at)));
  const terms = () => dealSides(d.give || [], d.get || [], { giveTitle: parent ? dealTr(T("What {0} gives"), v.a.name) : I18N.tr(T("I give")),
    getTitle: parent ? dealTr(T("What {0} gives"), v.b.name) : I18N.tr(T("I get")), meName: v.me.name, otherName: v.with.name });
  switch (m.kind) {
    case "offer": return bubble(h("b", "📨 ", T("Offer")), terms(), d.text ? C(d.text, "div.deal-say") : null);
    case "counter": return bubble(h("b", "↔ ", dealTr(T("Counter-offer (version {0})"), d.version)), terms(), d.text ? C(d.text, "div.deal-say") : null);
    case "accept": return bubble("✓ ", dealTr(T("Accepted version {0}"), d.version));
    case "reject": return bubble("✕ ", T("Rejected"), d.text ? C(" – " + d.text) : null);
    case "withdraw": return bubble(T("Withdrawn"));
    case "approval": return sys("⏳", I18N.tr(T("Waiting for a parent to allow it")));
    case "approved": return sys("👍", dealTr(T("{0} allowed the deal"), name));
    case "declined": return sys("✋", dealTr(T("{0} did not allow the deal"), name));
    case "stand": return sys("🤝", I18N.tr(T("The deal stands!")));
    case "chore": return sys("✅", dealTr(T("{0} done by {1}"), d.name, nameOf(d.doer)));
    case "coins": return sys("🪙", dealTr(T("{0} coins: {1} → {2}"), d.n, nameOf(d.giver), nameOf(d.receiver)));
    case "item": return sys("🎁", dealTr(T("{0} → {1}"), I18N.tr((d.item || {}).name || "?"), nameOf(d.receiver)));
    case "confirm": return bubble(T("Done ✓"));
    case "dispute": return bubble("✗ ", T("Not done"));
    case "council": return sys("🏛️", I18N.tr(T("Sent to the family council")));
    case "settled": return sys("⚖️", d.done ? I18N.tr(T("Decided: done")) : I18N.tr(T("Decided: not done")));
    case "done": return sys("🎉", I18N.tr(T("Deal done – everything is transferred.")));
    case "failed": return sys("❌", I18N.tr(DEAL_REASON[d.reason] || T("The deal failed")) + (d.chore ? " (" + d.chore + ")" : ""));
    case "cancelled": return sys("🛑", I18N.tr(T("A parent cancelled the deal")));
    default: return sys("•", m.kind);
  }
}

// ---------------------------------------------------------------- the offer builder (new offer or counter-offer)
async function dealBuilder({ to = null, deal = null, after = null } = {}) {
  let partners = [];
  if (!deal && !to) {
    try { partners = (await dealCall("me/deals")).partners || []; } catch (e) { return toast(e.message, "bad"); }
    if (!partners.length) return toast(T("Nobody to trade with right now"), "bad");
  }
  const st = { to: deal ? deal.with.id : to, give: deal ? deal.give.map(x => ({ ...x })) : [], get: deal ? deal.get.map(x => ({ ...x })) : [], assets: null };
  const msg = h("input", { type: "text", maxlength: 140, placeholder: T("Message (optional)"), "aria-label": T("Message (optional)") });
  const body = h("div.deal-builder");
  const m = modal(body, { wide: true });
  const load = async () => {
    if (!st.to) return draw();
    try { st.assets = await dealCall("me/deals/assets/" + st.to); } catch (e) { toast(e.message, "bad"); st.assets = null; }
    draw();
  };
  const kinds = () => (st.assets && st.assets.settings.kinds) || {};
  function sideBox(key) {
    const A = st.assets, mine = key === "give";
    const giver = mine ? A.me : A.other, taker = mine ? A.other : A.me;
    const list = st[key];
    const add = it => { list.push(it); draw(); };
    const btns = [];
    if (kinds().coins !== false) btns.push(h("button.btn.small.ghost", { onclick: () => pickCoins(add, mine ? A.me.coins : null) }, "🪙 ", T("Coins")));
    // «I give» a chore = I do a chore of the other one; «I get» a chore = the other one does mine
    if (kinds().chores !== false && (taker.chores || []).length) btns.push(h("button.btn.small.ghost", { onclick: () => pickChore(add, taker, giver) }, "🧹 ", T("Chore")));
    if (kinds().chores !== false && A.new_task && giver.role === "kid" && taker.role === "parent") btns.push(h("button.btn.small.ghost", { onclick: () => pickTask(add) }, "➕ ", T("New task")));
    const things = taker.role === "kid" ? [...(kinds().pets !== false ? (giver.pets || []).map(p => ({ t: "pet", id: p.id, kind: p.kind, name: p.name, emoji: p.emoji, ok: p.ok, why: p.why })) : []),
      ...(kinds().avatar !== false ? (giver.avatar || []).map(a => ({ t: "avatar", ...a, ok: true })) : []),
      ...(kinds().games !== false ? (giver.games || []).map(g => ({ t: "game", ...g, ok: true })) : [])] : [];
    if (things.length) btns.push(h("button.btn.small.ghost", { onclick: () => pickThing(add, things) }, "🎁 ", T("Thing")));
    if (kinds().text !== false) btns.push(h("button.btn.small.ghost", { onclick: () => pickText(add) }, "✍️ ", T("Free text")));
    return h("section.deal-build-side.deal-" + key,
      h("div.deal-side-h", mine ? T("I give") : T("I get")),
      list.length ? list.map((it, i) => dealItem(it, { owner: mine ? A.other.name : A.me.name, onRemove: () => { list.splice(i, 1); draw(); } }))
        : h("p.small.muted", mine ? T("What do you give?") : T("What do you want?")),
      h("div.row.deal-add", ...btns));
  }
  function draw() {
    const A = st.assets;
    body.replaceChildren(...[
      h("h2", deal ? T("Counter-offer") : T("New offer")),
      !deal ? h("div.deal-partners", ...partners.map(p => h("button.deal-partner" + (p.id === st.to ? ".on" : ""), { onclick: () => { st.to = p.id; st.give = []; st.get = []; load(); } },
        avatarSvg(p.avatar, 40), C(p.name, "span")))) : null,
      A ? [h("div.deal-with", T("Deal with"), " ", C(A.other.name, "b"), A.me.coins != null ? h("span.small.muted", "  ·  🪙 ", dealTr(T("{0} coins free"), fmt(A.me.coins))) : null),
        sideBox("give"), h("div.deal-swap-big", "⇅"), sideBox("get"), msg,
        h("div.row", h("button.btn", { disabled: !st.give.length || !st.get.length, onclick: send }, deal ? "↔ " : "📨 ", deal ? T("Send counter-offer") : T("Send offer")),
          h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))]
        : st.to ? h("p.muted", T("Loading…")) : h("p.muted", T("Who do you want to trade with?"))].flat().filter(Boolean));
  }
  const clean = it => { const { ok, why, ...x } = it; return x; };
  async function send(ev) {
    ev.currentTarget.disabled = true;
    try {
      const b = { give: st.give.map(clean), get: st.get.map(clean), text: msg.value };
      const r = deal ? await dealCall(`me/deals/${deal.id}/counter`, { method: "POST", body: { ...b, version: deal.version } })
        : await dealCall("me/deals", { method: "POST", body: { ...b, to: st.to } });
      m.close(); Sound.play("done"); toast(deal ? T("Counter-offer sent") : T("Offer sent"), "good");
      if (after) after(r);
    } catch (e) { if (!window.FQ_PARENT_AREA) toast(e.message, "bad"); ev.target.disabled = false; }
  }
  function pickCoins(add, have) {
    const max = Math.max(1, Math.min(have == null ? 100000 : Math.floor(have), (st.assets.settings || {}).max_coins || 100000));
    let n = Math.min(10, max);
    const num = h("b.deal-num");
    const show = () => { num.textContent = fmt(n); };
    const step = d => () => { n = Math.max(1, Math.min(max, n + d)); show(); };
    show();
    const p = modal(h("div.deal-pick", h("h3", "🪙 ", T("How many coins?")),
      h("div.row.deal-stepper", h("button.btn.ghost", { onclick: step(-10) }, "−10"), h("button.btn.ghost", { onclick: step(-1) }, "−"), num,
        h("button.btn.ghost", { onclick: step(1) }, "+"), h("button.btn.ghost", { onclick: step(10) }, "+10")),
      h("p.small.muted.center", dealTr(T("at most {0}"), fmt(max))),
      h("div.row", h("button.btn", { onclick: () => { p.close(); add({ t: "coins", n }); } }, T("Add")), h("button.btn.ghost", { onclick: () => p.close() }, T("Cancel")))));
  }
  function pickChore(add, owner, doer) {
    const p = modal(h("div.deal-pick", h("h3", "🧹 ", owner.id === st.assets.me.id ? T("Which of your chores?") : dealTr(T("Which chore of {0}?"), owner.name)),
      h("p.small.muted", doer.id === st.assets.me.id ? T("You do it instead – it moves to your chore list.") : dealTr(T("{0} does it instead of you."), doer.name)),
      ...owner.chores.map(c => h("button.deal-pick-row", { onclick: () => { p.close(); pickTimes(add, c, owner); } }, h("span.deal-emoji", c.icon),
        h("div.grow", C(c.name, "b"), h("div.small.muted", c.dates.slice(0, 3).map(dealDay).join(", "), c.points && c.account !== "xp" ? " · 🪙 " + fmt(c.points) : "")))),
      h("button.btn.ghost", { onclick: () => p.close() }, T("Cancel"))));
  }
  function pickTimes(add, c, owner) {
    let n = 1, to = "doer";
    const num = h("b.deal-num", "1"), dates = h("div.small.muted.center");
    const show = () => { num.textContent = n; dates.textContent = c.dates.slice(0, n).map(dealDay).join(", "); };
    const toBox = c.points && c.account !== "xp" ? h("div.deal-to", h("div.small", T("The chore's own coins go to …")),
      h("label.check", h("input", { type: "radio", name: "deal-to", checked: true, onchange: () => { to = "doer"; } }), T("who does it")),
      h("label.check", h("input", { type: "radio", name: "deal-to", onchange: () => { to = "owner"; } }), C(owner.name)),
      h("div.small.muted", T("XP always go to who does the chore."))) : null;
    show();
    const p = modal(h("div.deal-pick", h("h3", c.icon, " ", C(c.name)),
      c.max > 1 ? h("div.row.deal-stepper", h("button.btn.ghost", { onclick: () => { n = Math.max(1, n - 1); show(); } }, "−"), num, h("span", "×"),
        h("button.btn.ghost", { onclick: () => { n = Math.min(c.max, n + 1); show(); } }, "+")) : null, dates, toBox,
      h("div.row", h("button.btn", { onclick: () => { p.close(); add({ t: "chore", chore: c.chore, name: c.name, icon: c.icon, points: c.points, account: c.account, times: n, to, dates: c.dates.slice(0, n) }); } }, T("Add")),
        h("button.btn.ghost", { onclick: () => p.close() }, T("Cancel")))));
  }
  function pickThing(add, things) {
    const p = modal(h("div.deal-pick", h("h3", "🎁 ", T("Which thing?")),
      h("div.deal-things", ...things.map(it => h("button.deal-thing" + (it.ok ? "" : ".off"), { disabled: !it.ok, title: it.why || "",
        onclick: () => { p.close(); add(it); } }, dealPic(it, 44), it.t === "pet" ? C(it.name, "span") : h("span", it.name), it.why ? h("span.small.muted", it.why) : null))),
      h("button.btn.ghost", { onclick: () => p.close() }, T("Cancel"))));
  }
  function pickText(add) {
    const inp = h("input", { type: "text", maxlength: 140, placeholder: T("e.g. I help you with your homework") });
    const p = modal(h("div.deal-pick", h("h3", "✍️ ", T("Free deal")), h("p.small.muted", T("Without automation: at the end both confirm «Done ✓».")), inp,
      h("div.row", h("button.btn", { onclick: () => { if (!inp.value.trim()) return inp.focus(); p.close(); add({ t: "text", text: inp.value.trim() }); } }, T("Add")),
        h("button.btn.ghost", { onclick: () => p.close() }, T("Cancel")))));
    setTimeout(() => inp.focus(), 50);
  }
  function pickTask(add) {
    const name = h("input", { type: "text", maxlength: 60, placeholder: T("e.g. mow the lawn") });
    const icon = h("input.icon-in", { type: "text", value: "🌱", maxlength: 8 });
    const day = h("input", { type: "date", value: new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10) });
    const p = modal(h("div.deal-pick", h("h3", "➕ ", T("New task")), h("p.small.muted", T("A one-off chore for the child – done when a parent confirms it.")),
      h("div.row", icon, h("label.field.grow", T("Name"), name)), h("label.field", T("Date"), day),
      h("div.row", h("button.btn", { onclick: () => { if (!name.value.trim()) return name.focus(); p.close();
        add({ t: "newchore", name: name.value.trim(), icon: icon.value || "🧹", date: day.value }); } }, T("Add")),
        h("button.btn.ghost", { onclick: () => p.close() }, T("Cancel")))));
  }
  draw();
  load();
}

// ---------------------------------------------------------------- the children's app: #/deals and #/deals/<id>
async function dealsView(arg) {
  if (arg) return dealView(+arg);
  let d;
  try { d = await api("me/deals"); } catch (e) { return toast(e.message, "bad"); }
  let ended = null;
  const endBox = h("div");
  const showEnded = async () => {
    try { ended = (await api("me/deals?ended=true")).deals; } catch { ended = []; }
    endBox.replaceChildren(...(ended.length ? ended.map(v => dealCard(v, x => go("deals/" + x.id))) : [h("p.small.muted", T("Nothing yet."))]));
  };
  const turn = d.deals.filter(v => v.turn), rest = d.deals.filter(v => !v.turn);
  screen("deals", { actions: d.on ? h("button.btn.small", { onclick: () => dealBuilder({ after: r => go("deals/" + r.id) }) }, "+ ", T("Offer")) : null },
    h("section.card.deal-intro", h("h2", "🤝 ", T("Deals")),
      h("p.small.muted", T("Trade coins, chores, things or favours – with your siblings or your parents. XP cannot be traded.")),
      d.on ? h("button.btn", { onclick: () => dealBuilder({ after: r => go("deals/" + r.id) }) }, "📨 ", T("New offer")) : h("p.bad-text", T("Trading is switched off for you"))),
    turn.length ? h("section", h("h3", "🔔 ", T("Waiting for your answer")), ...turn.map(v => dealCard(v, x => go("deals/" + x.id)))) : null,
    h("section", h("h3", T("Running")), ...(rest.length ? rest.map(v => dealCard(v, x => go("deals/" + x.id))) : [h("p.small.muted", T("No running deals."))])),
    h("section", h("button.link", { onclick: e => { e.currentTarget.remove(); showEnded(); } }, "📜 ", T("Finished deals")), endBox));
}

async function dealView(id) {
  let v;
  try { v = await api("me/deals/" + id); } catch (e) { toast(e.message, "bad"); return go("deals"); }
  const box = h("section.card");
  const draw = x => { v = x; box.replaceChildren(dealThreadEl(v, { refresh: () => { S.keepScroll = window.scrollY; route(); } })); };   // anew: menu badge too
  draw(v);
  screen("deals", { back: () => go("deals") }, box);
  // a new message of the other one appears by itself
  const at = location.hash;
  const timer = setInterval(async () => {
    if (location.hash !== at || !box.isConnected) return clearInterval(timer);
    if (document.hidden || document.querySelector(".modal-back")) return;
    try { const n = await api("me/deals/" + id); if ((n.messages || []).length !== (v.messages || []).length || n.status !== v.status) draw(n); } catch {}
  }, 8000);
}

// a short note below the header: a new offer, a counter-offer, the deal stands … (like «somebody opened a table»)
const DEAL_NOTE_TEXT = { offer: T("New offer from {0}"), counter: T("Counter-offer from {0}"), accept: T("{0} accepted"), stand: T("Deal with {0} stands!"),
  reject: T("{0} rejected your offer"), withdraw: T("{0} withdrew the offer"), done: T("Deal with {0} is done"), failed: T("Deal with {0} failed"),
  cancelled: T("Deal with {0} was cancelled"), approval: T("Deal with {0} waits for parents"), approved: T("Deal with {0} stands!"),
  declined: T("Deal with {0} was not allowed"), chore: T("Deal with {0}: a chore is done"), coins: T("Deal with {0}: coins transferred"),
  item: T("Deal with {0}: something changed hands"), confirm: T("{0} confirmed the free deal"), dispute: T("{0} says: not done"),
  council: T("Deal with {0}: family council"), settled: T("Deal with {0} was decided") };
function dealNote(sum) {
  if (!sum || !sum.notes || !sum.notes.length || typeof S === "undefined" || !S.me || document.querySelector(".table-note")) return;
  let shown = [];
  try { shown = JSON.parse(sessionStorage.getItem("fq.deals.noted") || "[]"); } catch {}
  const n = sum.notes.find(x => !shown.includes(x.msg));
  if (!n) return;
  shown.push(n.msg);
  try { sessionStorage.setItem("fq.deals.noted", JSON.stringify(shown.slice(-50))); } catch {}
  const txt = dealTr(DEAL_NOTE_TEXT[n.kind] || T("Deal with {0}"), n.with);
  const close = () => { box.classList.remove("on"); setTimeout(() => box.remove(), 300); };
  const box = h("div.table-note.deal-note", { role: "status" }, h("span.table-note-ic", "🤝"), h("span.table-note-txt", { title: txt }, txt),
    h("button.btn.small", { onclick: () => { close(); go("deals/" + n.deal); } }, T("Open")),
    h("button.icon-btn", { title: T("Close"), "aria-label": T("Close"), onclick: close }, "✕"));
  const top = document.querySelector(".top");
  box.style.top = Math.max(8, Math.round(top ? top.getBoundingClientRect().bottom : 0) + 6) + "px";
  document.body.append(box);
  if (typeof tableNote === "object") tableNote.box = box;      // gone on the next navigation, like the table note (kid.js)
  requestAnimationFrame(() => box.classList.add("on"));
  try { Sound.play("turn"); } catch {}
  setTimeout(close, 9000);
}

// ---------------------------------------------------------------- parent area: tab «Deals»
async function dealsParentView(main) {
  const [ov, mine] = await Promise.all([call("parent/deals"), call("me/deals")]);
  const open = v => dealParentThread(v.id, v.a ? true : false);
  const appr = ov.deals.filter(v => v.status === "approval");
  const running = ov.deals.filter(v => ["open", "running"].includes(v.status));
  const ended = ov.deals.filter(v => !["open", "running", "approval"].includes(v.status));
  const row = v => h("li.row.deal-prow", avatarSvg(v.a.avatar, 30), C(v.a.name, "b"), h("span", "⇄"), avatarSvg(v.b.avatar, 30), C(v.b.name, "b"),
    dealStatusChip({ ...v, turn: false, with: v.b }), h("span.grow.small.muted", fmtDateTime(v.updated_at)),
    h("button.btn.small.ghost", { onclick: () => open(v) }, T("Open")));
  main.append(pageHead("🤝 " + I18N.tr(T("Deals")), h("button.btn", { onclick: () => dealBuilder({ after: () => render() }) }, "+ ", T("New offer"))),
    h("p.muted", T("Children trade coins, chores, pets, avatar items, bought games and favours – with each other and with you. XP can never be traded. Reserved coins cannot be spent until the deal is done or fails.")),
    appr.length ? section("⏳ " + I18N.tr(T("Waiting for your OK")), h("ul.list", ...appr.map(row))) : null,
    section("👤 " + I18N.tr(T("My deals")), mine.deals.length ? h("div.deal-list", ...mine.deals.map(v => dealCard(v, x => dealParentThread(x.id, false))))
      : h("p.small.muted", T("No running deals."))),
    section("📋 " + I18N.tr(T("All running deals")), running.length ? h("ul.list", ...running.map(row)) : h("p.small.muted", T("No running deals."))),
    section("📜 " + I18N.tr(T("Finished deals")), ended.length ? h("ul.list", ...ended.slice(0, 40).map(row)) : h("p.small.muted", T("Nothing yet."))),
    dealSettingsBox(ov.settings, ov.kids));
}

async function dealParentThread(id, overview) {
  let v;
  try { v = overview ? await call("parent/deals/" + id) : await call("me/deals/" + id); } catch { return; }
  const box = h("div");
  const m = modal(box, { wide: true, onClose: () => render() });
  const draw = x => box.replaceChildren(dealThreadEl(x, { parent: overview, refresh: r => { if (r && r.messages) draw(overview ? { ...r, a: r.me, b: r.with } : r); else { m.close(); } } }),
    h("div.row", h("button.btn.ghost", { onclick: () => m.close() }, T("Close"))));
  draw(v);
}

function dealSettingsBox(s, kids) {
  const on = h("input", { type: "checkbox", checked: s.on });
  const kidBoxes = kids.map(k => h("label.check", h("input", { type: "checkbox", value: k.id, checked: !s.off.includes(k.id) }), C(k.name)));
  const names = { coins: "🪙 " + I18N.tr(T("Coins")), chores: "🧹 " + I18N.tr(T("Chores")), pets: "🐾 " + I18N.tr(T("Pets")), avatar: "🎩 " + I18N.tr(T("Avatar items")),
    games: "🎮 " + I18N.tr(T("Bought games")), text: "✍️ " + I18N.tr(T("Free deals")) };
  const kinds = Object.keys(names).map(k => h("label.check", h("input", { type: "checkbox", value: k, checked: s.kinds[k] !== false }), names[k]));
  const max = h("input", { type: "number", min: 1, max: 100000, value: s.max_coins });
  const appr = h("input", { type: "checkbox", checked: s.approval });
  const thr = h("input", { type: "number", min: 1, max: 100000, value: s.threshold });
  const pets = h("input", { type: "checkbox", checked: s.approval_pets });
  const save = async () => {
    await call("parent/deals/settings", { method: "PUT", body: { on: on.checked,
      off: kidBoxes.map(l => l.querySelector("input")).filter(x => !x.checked).map(x => +x.value),
      kinds: Object.fromEntries(kinds.map(l => l.querySelector("input")).map(x => [x.value, x.checked])),
      max_coins: Math.max(1, Math.round(+max.value || 1)), approval: appr.checked, threshold: Math.max(1, Math.round(+thr.value || 1)), approval_pets: pets.checked } });
    toast(T("Saved"), "good");
  };
  return section("⚙️ " + I18N.tr(T("Deal settings")),
    h("label.check", on, T("Trading is on")),
    h("div", h("strong", T("Children who may trade")), h("div.row", ...kidBoxes)),
    h("div", h("strong", T("What can be traded")), h("div.row", ...kinds), h("p.small.muted", T("XP can never be traded. Rented games neither – only games bought for good."))),
    h("div.grid2", h("label.field", h("span", "🪙 ", T("Max coins per deal")), max, h("span.hint", T("Coins children give in one deal, together."))),
      h("label.field", h("span", "⚖️ ", T("Approval from (coins)")), thr, h("span.hint", T("Deals between children with this many coins or more wait for a parent's OK.")))),
    h("label.check", appr, T("Big deals need a parent's approval")),
    h("label.check", pets, T("Deals with pets always need a parent's approval")),
    h("p.small.muted", T("A deal with a parent never needs approval.")),
    h("button.btn.small", { onclick: () => save().catch(() => {}) }, "💾 ", T("Save")));
}
