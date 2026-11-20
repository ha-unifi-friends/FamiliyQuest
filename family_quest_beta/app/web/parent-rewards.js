// ---------------------------------------------------------------- 🏆 Points and rules (rewards page)
// A part of the parent area (parent.js): loaded after it, before boot() runs (eltern.html).
"use strict";

// ---------------------------------------------------------------- rewards: accounts, rules, shop
// phones: a table with class «stack» shows each row as a small card – every cell gets its column name (also rows added later)
function stackTable(table) {
  const names = [...table.querySelectorAll("thead th")].map(th => { const c = th.cloneNode(true); c.querySelectorAll(".info-btn").forEach(x => x.remove()); return I18N.tr(c.textContent.trim()); });
  const label = tr => [...tr.children].forEach((td, i) => { if (names[i]) td.dataset.label = names[i]; });
  table.querySelectorAll("tbody tr").forEach(label);
  new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => { if (n.nodeName === "TR") label(n); }))).observe(table.tBodies[0], { childList: true });
  return table;
}

async function rewardsView(main, opts = {}) {
  const [accounts, rules, rewards] = await Promise.all([call("parent/accounts"), call("parent/rules"), call("parent/rewards")]);
  P.accounts = accounts;
  const accOpts = sel => accounts.map(a => h("option", { value: a.key, selected: a.key === sel }, (a.icon || "") + " " + I18N.tr(a.name)));

  const accRows = accounts.map(a => {
    // every field has its name for screen readers (the visible caption is the column head)
    const f = { name: h("input", { type: "text", value: I18N.tr(a.name), "aria-label": T("Name") }), unit: h("input", { type: "text", value: a.unit, "aria-label": T("Unit") }),
      icon: h("input", { type: "text", value: a.icon, "aria-label": T("Icon") }),
      spendable: h("input", { type: "checkbox", checked: !!a.spendable, disabled: a.key === "xp", "aria-label": T("Spendable") }),
      active: h("input", { type: "checkbox", checked: !!a.active, disabled: a.key === "xp", "aria-label": T("Active") }) };
    const save = () => call("parent/accounts", { method: "PUT", body: { key: a.key, name: f.name.value, unit: f.unit.value, icon: f.icon.value,
      spendable: f.spendable.checked, active: f.active.checked, sort: a.sort } }).then(() => toast(T("Saved"), "good"));
    Object.values(f).forEach(x => x.addEventListener("change", save));
    return h("tr", h("td.key-col", { translate: "no" }, h("code", a.key)), h("td", f.icon), h("td", f.name), h("td", f.unit), h("td.c", f.spendable), h("td.c", f.active));
  });
  const newAcc = h("input", { type: "text", placeholder: T("key, e.g. stars") });

  const ruleRows = rules.map(r => ruleRow(r));
  function ruleRow(r) {
    const f = { event: h("select", { "aria-label": T("Event") }, ...Object.entries(P.meta.events).map(([k, n]) => h("option", { value: k, selected: k === r.event }, n))),
      account: h("select", { "aria-label": T("Account") }, ...accOpts(r.account)), amount: h("input", { type: "number", value: r.amount, step: "1", "aria-label": T("Amount") }),
      daily_limit: h("input", { type: "number", value: r.daily_limit ?? "", placeholder: "–", "aria-label": T("Daily limit") }),
      label: h("input", { type: "text", value: I18N.tr(r.label || ""), "aria-label": T("Label") }),
      active: h("input", { type: "checkbox", checked: !!r.active, "aria-label": T("Active") }) };
    const save = () => call(r.id ? `parent/rules/${r.id}` : "parent/rules", { method: r.id ? "PUT" : "POST", body: { event: f.event.value, account: f.account.value,
      amount: +f.amount.value, daily_limit: f.daily_limit.value === "" ? null : +f.daily_limit.value, condition: r.condition || {}, label: f.label.value, active: f.active.checked } })
      .then(x => { if (!r.id && x) r.id = x.id; toast(T("Saved"), "good"); });
    Object.values(f).forEach(x => x.addEventListener("change", save));
    return h("tr", h("td", f.event), h("td.num", f.amount), h("td", f.account), h("td.num", f.daily_limit), h("td", f.label), h("td.c", f.active),
      h("td", h("button.icon-btn", { title: T("Delete"), "aria-label": T("Delete"), onclick: async e => { if (r.id) await call(`parent/rules/${r.id}`, { method: "DELETE" }); e.target.closest("tr").remove(); } }, "✕")));
  }
  const rulesBody = h("tbody", ...ruleRows);

  const rewardCards = rewards.map(r => rewardCard(r));
  function rewardCard(r) {
    const f = { icon: h("input.icon-in", { type: "text", value: r.icon, "aria-label": T("Icon") }), name: h("input", { type: "text", value: I18N.tr(r.name) }),   // built-in names are English keys – show (and save) the translation the children see
      kind: h("select", ...Object.entries(KIND_NAMES).map(([k, n]) => h("option", { value: k, selected: k === r.kind }, n))),
      account: h("select", ...accOpts(r.account)), cost: h("input", { type: "number", min: 0, value: r.cost }),
      approval: h("input", { type: "checkbox", checked: !!r.approval }), weekly_limit: h("input", { type: "number", min: 0, value: r.weekly_limit ?? "", placeholder: "–" }),
      active: h("input", { type: "checkbox", checked: !!r.active }), cfg: h("input", { type: "text" }) };
    const cfgLabel = h("span");
    const cfgKey = () => ({ internet_minutes: "minutes", planer_points: "points", ha_script: "script", avatar_item: "item" })[f.kind.value];
    const drawCfg = () => { const k = cfgKey(); cfgLabel.textContent = k ? I18N.tr({ minutes: T("Minutes"), points: T("Points"), script: T("Script (script.xyz)"), item: T("Avatar item id") }[k]) : ""; f.cfg.hidden = !k; f.cfg.value = k ? (r.config || {})[k] ?? "" : ""; };
    f.kind.addEventListener("change", drawCfg); drawCfg();
    const save = async () => {
      const k = cfgKey(); const config = {}; if (k && f.cfg.value !== "") config[k] = ["minutes", "points"].includes(k) ? +f.cfg.value : f.cfg.value;
      const body = { name: f.name.value, kind: f.kind.value, account: f.account.value, cost: +f.cost.value, approval: f.approval.checked,
        weekly_limit: f.weekly_limit.value === "" ? null : +f.weekly_limit.value, icon: f.icon.value || "🎁", config, active: f.active.checked, sort: r.sort || 0 };
      const x = await call(r.id ? `parent/rewards/${r.id}` : "parent/rewards", { method: r.id ? "PUT" : "POST", body });
      if (!r.id && x) r.id = x.id; r.config = config; toast(T("Saved"), "good");
    };
    return h("div.card.reward-ed" + (r.active ? "" : ".off"),
      h("div.row", f.icon, h("label.field.grow", T("Name"), f.name)),
      h("div.grid3", h("label.field", T("Type"), f.kind), h("label.field", T("Paid from"), f.account), h("label.field", T("Price"), f.cost),
        h("label.field", T("Max. per week"), f.weekly_limit), h("label.field", cfgLabel, f.cfg),
        h("div", h("label.check", f.approval, T("Parents must approve")), h("label.check", f.active, T("In the shop")))),
      h("button.btn.small", { onclick: save }, T("Save")));
  }
  const rewardBox = h("div.reward-grid", ...rewardCards);

  // the page of the points: accounts and the rules what gives how much (the rewards themselves are in «Shop»)
  const accBox = sectionAdd("🪙 " + I18N.tr(T("Accounts")), h("button.btn.small", { onclick: () => {
        const m = modal(h("div.form", h("h2", "+ ", T("Add account")), h("label.field", T("Key"), newAcc), h("p.small.muted", T("Short name without spaces, e.g. stars – the name and icon can be changed afterwards.")),
          h("div.row", h("button.btn", { onclick: async () => { const k = newAcc.value.trim().toLowerCase(); if (!k) return newAcc.focus();
            await call("parent/accounts", { method: "PUT", body: { key: k, name: k, unit: "", icon: "⭐", spendable: true, active: true, sort: 9 } }); m.close(); render(); } }, "💾 ", T("Save")),
            h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
        newAcc.focus();
      } }, "+ ", T("Add account")),
      h("div.scroll", stackTable(h("table.tbl.stack", h("thead", h("tr", h("th.key-col", T("Key"), fieldInfo(T("The short internal name of the account, without spaces – rules and rewards use it."))), h("th", "Icon"), h("th", T("Name")),
        h("th", T("Unit"), fieldInfo(T("What the points of this account are called, e.g. «min» – shown next to the amounts."))),
        h("th", T("Spendable"), fieldInfo(T("XP shows progress and is never spent. Spendable accounts can be used in the shop."))),
        h("th", T("Active"), fieldInfo(T("An inactive account is hidden in the app and nothing is booked on it any more – what it holds is kept."))))), h("tbody", ...accRows)))));
  accBox.dataset.fold = "accounts";
  accBox.dataset.status = accounts.filter(a => a.active).map(a => (a.icon || "") + " " + I18N.tr(a.name)).join(" · ");
  const rulesBox = sectionAdd("📏 " + I18N.tr(T("Rules: which action gives how much on which account")),
      h("button.btn.small", { onclick: () => rulesBody.append(ruleRow({ event: "lesson_done", account: "coins", amount: 5, daily_limit: null, label: "", active: 1, condition: {} })) }, "+ ", T("Add rule")),
      h("div.scroll", stackTable(h("table.tbl.stack", h("thead", h("tr", h("th", T("Event"), fieldInfo(T("What gives the points: a right answer, a finished lesson, the daily goal, a chore …"))),
        h("th", T("Amount"), fieldInfo(T("How many points one such event gives; a negative amount takes points away."))), h("th", T("Account")),
        h("th", T("Daily limit"), fieldInfo(T("The most points this rule gives a child per day. Empty = no limit."))),
        h("th", T("Label"), fieldInfo(T("An own name for the rule, e.g. in the list of points – empty: the name of the event."))),
        h("th", T("Active"), fieldInfo(T("An inactive rule gives no points until you switch it on again."))), h("th"))), rulesBody))));
  rulesBox.dataset.fold = "rules";
  rulesBox.dataset.status = I18N.tr(T("Rules: {0} · active: {1}")).replace("{0}", rules.length).replace("{1}", rules.filter(r => r.active).length);
  if (opts.onlyShop) return { rewardBox, rewardCard };
  main.append(h("h1", T("Points & rules")),
    h("p.muted.rew-shop-note", T("What children buy with their points – vouchers, internet minutes, avatar items – is set in the shop."), " ",
      h("button.btn.small.ghost", { onclick: () => { P.tab = "shop"; location.hash = "shop"; render(); } }, "🛍️ ", T("Open the shop settings"))),
    accBox, rulesBox);
  foldBoxes(main, "rew");
}
