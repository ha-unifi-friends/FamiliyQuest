// ---------------------------------------------------------------- 📜 History: everything that happened, one list
// A part of the parent area (parent.js): loaded after it, before boot() runs (eltern.html).
"use strict";

// ---------------------------------------------------------------- 📜 History: everything that happened, one list
// points and coins (ledger), shop rewards (redemptions) and the family history (games, quiz wins, council decisions …) –
// for one child or everybody, filtered by kind; the newest first
const HIST_KINDS = () => [["all", "📜", T("Everything")], ["points", "🪙", T("Points & coins")], ["rewards", "🎁", T("Rewards")], ["family", "👨‍👩‍👧", T("Games & family")]];
async function historyView(main) {
  const [profiles, accounts] = await Promise.all([call("parent/profiles"), call("parent/accounts")]);
  P.accounts = accounts;
  const people = [...profiles.filter(p => p.role === "kid"), ...profiles.filter(p => p.role !== "kid")];
  if (P.histWho == null) P.histWho = people.length ? String(people[0].id) : "all";
  P.histKind = P.histKind || "all";
  const who = h("select", { "aria-label": T("Profile"), onchange: () => { P.histWho = who.value; load(); } },
    h("option", { value: "all", selected: P.histWho === "all" }, I18N.tr(T("Everybody"))),
    ...people.map(p => h("option", { value: p.id, selected: String(p.id) === P.histWho }, p.name)));
  const kinds = h("div.seg.hist-kinds", { role: "radiogroup", "aria-label": T("Show") });
  const drawKinds = () => kinds.replaceChildren(...HIST_KINDS().map(([k, ic, n]) => h("button" + (P.histKind === k ? ".on" : ""), { type: "button", role: "radio",
    "aria-checked": String(P.histKind === k), onclick: () => { P.histKind = k; drawKinds(); load(); } }, ic + " ", n)));
  drawKinds();
  const box = h("div.hist-box");
  const acc = k => accounts.find(a => a.key === k) || { icon: "", name: k };
  const when = at => new Date(String(at).replace(" ", "T")).toLocaleString(I18N.locale, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  const STATUS = { pending: ["⏳", T("Waiting")], approved: ["✓", T("Approved")], rejected: ["✗", T("Declined")], failed: ["⚠️", T("Failed")] };
  async function rows(p) {
    const k = P.histKind, out = [];
    const [led, red, fam] = await Promise.all([
      k === "all" || k === "points" ? call(`parent/ledger/${p.id}`).catch(() => []) : [],
      k === "all" || k === "rewards" ? call(`parent/redemptions?profile_id=${p.id}`).catch(() => []) : [],
      k === "all" || k === "family" ? api(`community/history?profile_id=${p.id}`).catch(() => []) : []]);
    for (const r of led) {
      const a = acc(r.account);
      out.push({ at: r.at, ic: a.icon || "🪙", who: p.name, txt: I18N.tr(r.reason || r.event || ""),
        extra: (r.amount > 0 ? "+" : "") + fmt(r.amount, 1) + " " + I18N.tr(a.name), cls: r.amount < 0 ? "bad" : "good" });
    }
    for (const r of red) {
      const [sic, sn] = STATUS[r.status] || ["", r.status];
      out.push({ at: r.created_at, ic: r.icon || "🎁", who: p.name, txt: r.name, own: true, extra: "−" + fmt(r.cost) + " · " + sic + " " + I18N.tr(sn) });
    }
    for (const e of fam) { const [ic, txt, extra] = historyText(e); out.push({ at: e.at, ic, who: p.name, txt, own: true, extra: extra || "" }); }
    return out;
  }
  async function load() {
    box.replaceChildren(h("p.muted", "…"));
    const list = (await Promise.all((P.histWho === "all" ? people : people.filter(p => String(p.id) === P.histWho)).map(rows))).flat()
      .sort((a, b) => String(b.at).localeCompare(String(a.at)));
    if (!list.length) return box.replaceChildren(h("p.muted", T("Nothing yet.")));
    const ul = h("ul.list.history"), PAGE = 50;
    let n = 0;
    const more = h("button.btn.small.ghost.history-more", { onclick: () => page() }, T("Show more"));
    const line = e => h("li.row", h("span.big-ic", e.ic), h("span.grow", e.own ? h("span", { translate: "no" }, e.txt) : h("span", e.txt),
        P.histWho === "all" ? h("span.small.muted", { translate: "no" }, " · " + e.who) : null),
      e.extra ? h("b" + (e.cls ? "." + e.cls + "-text" : ""), " ", e.extra) : null, h("span.small.muted", " " + when(e.at)));
    const page = () => { ul.append(...list.slice(n, n + PAGE).map(line)); n += PAGE; more.hidden = n >= list.length; };
    page();
    box.replaceChildren(ul, more);
  }
  main.append(pageHead(T("History")), h("div.row.wrap.hist-filter", who, kinds), h("section.card.sec.hist-box", box));
  load();
}
