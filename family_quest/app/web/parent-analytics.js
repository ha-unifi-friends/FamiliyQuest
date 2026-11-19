// ---------------------------------------------------------------- 📈 Analytics in the parent area
// Two tabs: «Dashboards» (the standard dashboard and own ones – tiles of reports on a grid, one timeline filter for all
// tiles) and «Reports» (templates, «My reports» and the ad-hoc report: drag dimensions and measures into Columns, Rows,
// Data and Group – with pointer events, so it works with a finger; or tap a chip, then tap a zone).
// The server only knows a whitelist (familyquest/analytics.py); every chart is our own inline SVG (no library).
// Loaded after parent.js and parent-info.js: adds the menu item, its ⓘ texts and analyticsView.
"use strict";

TABS.splice(1, 0, ["analytics", "📈", T("Analytics")]);

Object.assign(PARENT_INFO, {
  [T("Analytics")]: [
    T("Reports about your family's data: coins and points, learning, games, chores, rewards, game time, the game battery and the weather of the day."),
    T("«Dashboards» shows several reports at once for one period – the standard dashboard or your own ones. «Reports» has the templates, your saved reports and the ad-hoc report to build your own.")],
  [T("Dashboards")]: [
    T("A dashboard shows several reports side by side. The timeline at the top chooses the period for every tile: tap the calendar or the title for a range, ◀ ▶ step back and forward, «Now» goes back to today, ⋮ chooses day, week, month, year or 12 months."),
    T("«Edit» lets you add reports (drag them from the list or tap «+ Add report»), move tiles (drag ⠿ or tap ◀ ▶), change their size (drag the corner or tap ↔ ↕), give a tile its own title or remove it. On phones every tile takes the whole width.")],
  [T("Templates")]: T("Ready-made reports: tap one and it fills the ad-hoc report below – change it as you like and save it under «My reports»."),
  [T("My reports")]: T("The reports you saved. Tap one to open it; ✏️ renames it, 🗑️ removes it. They are part of the backup."),
  [T("Ad-hoc report")]: [
    T("Choose the data source, then drag dimensions (person, day, week, game …) and measures (count, coins, minutes …) into the zones – or tap a chip and then a zone. × removes a chip, drag it to change the order."),
    T("Rows: the categories (the x-axis of a chart). Columns: the series (colours, the columns of the pivot). Group: one table or chart per value. Data: the numbers – with several, every chart shows one of them."),
    T("At most 3 dimensions and 4 measures. Private books are never counted and no titles of books are shown.")],
  [T("Add report")]: T("Choose a template or one of your saved reports – it is added at the end of the dashboard."),
});

// ---------------------------------------------------------------- names of what the server knows
const AN_DATASETS = { ledger: ["🪙", T("Points & coins")], learning: ["📚", T("Learning answers")], daily: ["⭐", T("Learning days")],
  games: ["🎲", T("Games played")], chores: ["🧹", T("Chores")], rewards: ["🎁", T("Rewards redeemed")], gametime: ["🎮", T("Game time")],
  battery: ["🔋", T("Game battery")], weather: ["☀️", T("Weather of the day")], reading: ["📖", T("Books read")] };
const AN_DIMS = { child: ["👤", T("Person")], day: ["📅", T("Day")], week: ["🗓️", T("Week")], month: ["🗓️", T("Month")], year: ["🗓️", T("Year")],
  weekday: ["📆", T("Weekday")], account: ["🏦", T("Account")], event: ["🏷️", T("Category")], subject: ["📚", T("Subject")],
  exercise: ["✏️", T("Exercise type")], game: ["🎲", T("Game")], chore: ["🧹", T("Chore")], status: ["🚦", T("Status")],
  chore_kind: ["🏷️", T("Duty or bonus")], reward: ["🎁", T("Reward")], reward_kind: ["🏷️", T("Reward type")],
  battery_kind: ["🔋", T("Battery event")], weather: ["☀️", T("Weather")], book_type: ["📖", T("Book type")] };
const AN_MEASURES = { count: T("Count"), coins: T("Coins"), coins_earned: T("Coins earned"), coins_spent: T("Coins spent"), xp: "XP",
  internet_used: T("Internet minutes used"), amount: T("Amount (all accounts)"), answers: T("Answers"), correct: T("Correct answers"),
  wrong: T("Wrong answers"), accuracy: T("Accuracy %"), minutes: T("Minutes"), lessons: T("Lessons"), goal_days: T("Days with daily goal"),
  days: T("Days"), wins: T("Wins"), avg_place: T("Average place"), done: T("Done"), open: T("Not done"), rate: T("Done %"), points: T("Points"),
  approved: T("Approved"), cost: T("Cost"), hours: T("Hours"), starts: T("Game starts"), used: T("Segments used"),
  charged: T("Segments charged"), bonus: T("Bonus points"), malus: T("Malus points"), books: T("Books"), finished: T("Finished"),
  rating: T("Average rating") };
const AN_NOT_ADDITIVE = new Set(["accuracy", "rate", "avg_place", "rating"]);      // no totals for averages
const AN_VALUES = {
  status: { open: T("Not done"), pending: T("Waiting"), done: T("Done"), approved: T("Approved"), rejected: T("Declined"), failed: T("Failed") },
  chore_kind: { duty: T("Duty"), bonus: T("Bonus") },
  battery_kind: { start: T("Game start"), recharge: T("Recharge"), goal: T("Goal"), chore: T("Chore"), parent: T("Parent") },
  book_type: { picture: T("Picture book"), adventure: T("Interactive book"), game: T("Adventure game") },
};
const AN_CHARTS = [
  ["table", T("Data table"), "M3 5h18v14H3zM3 10h18M3 15h18M9 5v14"],
  ["pivot", T("Pivot"), "M3 5h18v14H3zM8 5v14M3 9h18M14 9v10"],
  ["bar", T("Bars"), "M4 20V11M8 20V6M13 20V13M17 20V8M3 20h18"],
  ["stacked", T("Stacked bars"), "M5 20V13M5 13V8M11 20V15M11 15V5M17 20V12M17 12V9M3 20h18"],
  ["stacked100", T("100 % stacked"), "M5 20V12M5 12V4M11 20V8M11 8V4M17 20V15M17 15V4M3 20h18"],
  ["line", T("Line"), "M3 17l5-6 4 3 4-7 5 4M3 20h18"],
  ["area", T("Area"), "M3 20V15l5-6 4 3 4-7 5 4v11z"],
  ["pie", T("Donut"), "M12 3a9 9 0 1 0 9 9h-9zM14 3.3A9 9 0 0 1 20.7 10H14z"],
];
const AN_RANGES = [["7d", T("7 days")], ["30d", T("30 days")], ["year", T("This year")], ["all", T("All")]];
const AN_HEIGHTS = { s: 170, m: 250, l: 360 };

const AN = { meta: null, tab: "dash", spec: null, loaded: null, sel: null, dash: null, edit: false };
const anStore = { get(k, d) { try { const v = localStorage.getItem("fq.an." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("fq.an." + k, JSON.stringify(v)); } catch { /* private window */ } } };
const anTr = k => I18N.tr(k);
const anSvg = (tag, attrs = {}) => { const el = document.createElementNS("http://www.w3.org/2000/svg", tag); for (const [k, v] of Object.entries(attrs)) if (v != null) el.setAttribute(k, v); return el; };
const anIcon = d => { const s = anSvg("svg", { viewBox: "0 0 24 24", width: 22, height: 22, "aria-hidden": "true" }); s.append(anSvg("path", { d, fill: "none", stroke: "currentColor", "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round" })); return s; };
const anDimName = k => (AN_DIMS[k] || ["", k])[1];
const anMeasureName = k => AN_MEASURES[k] || k;

// ---------------------------------------------------------------- the page
async function analyticsView(main) {
  AN.meta = await call("parent/analytics/meta");
  if (!AN.spec) AN.spec = { dataset: "ledger", columns: [], rows: [], group: [], data: [], range: "30d", profiles: [], chart: "bar" };
  AN.tab = anStore.get("tab", "dash");
  if (!AN.openedOnce) { SET_OPEN.add("an.tpl"); AN.openedOnce = true; }
  const dash = h("div.an-dashpane"), rep = h("div.an-reppane");
  const tabs = tabbed([{ key: "dash", label: "📊 " + anTr(T("Dashboards")), content: [dash] }, { key: "rep", label: "📋 " + anTr(T("Reports")), content: [rep] }]);
  tabs.bar.addEventListener("click", e => { const b = e.target.closest(".tab"); if (b) anStore.set("tab", AN.tab = b.id === "tab-rep" ? "rep" : "dash"); });
  main.append(h("h1", "📈 ", T("Analytics")), h("div.an-root", tabs.el));
  AN.showTab = k => { tabs.show(k); anStore.set("tab", AN.tab = k); };
  tabs.show(AN.tab);
  anReportsPane(rep);
  anDashPane(dash);
}

// ================================================================ Reports tab
function anReportsPane(root) {
  const tplBox = h("section.card.sec", h("h2", T("Templates")), h("div.an-tpls", ...AN.meta.templates.map(t =>
    h("button.an-tpl", { type: "button", onclick: () => anLoad(t.spec, { kind: "t", id: t.key, name: t.title }) }, h("span.an-tpl-ic", t.icon), h("span", t.title)))));
  const mineList = h("div.an-tpls.an-mine");
  const mineBox = h("section.card.sec", h("h2", T("My reports")), mineList);
  const drawMine = () => {
    const items = AN.meta.reports;
    mineList.replaceChildren(...(items.length ? items.map(r => h("div.an-mine-item",
      h("button.an-tpl", { type: "button", onclick: () => anLoad(r.spec, { kind: "r", id: r.id, name: r.name }) },
        h("span.an-tpl-ic", (AN_DATASETS[r.spec.dataset] || ["📈"])[0]), C(r.name)),
      h("button.icon-btn", { type: "button", title: T("Rename"), "aria-label": T("Rename"), onclick: async () => {
        const n = await promptDialog(T("Name of the report"), r.name, { maxLength: 60 });
        if (n == null || !n.trim()) return;
        try { Object.assign(r, await call(`parent/analytics/reports/${r.id}`, { method: "PUT", body: { name: n } })); drawMine(); } catch {}
      } }, "✏️"),
      h("button.icon-btn", { type: "button", title: T("Delete"), "aria-label": T("Delete"), onclick: async () => {
        if (!await confirmDialog(I18N.tr(T("Delete the report «{0}»?")).replace("{0}", r.name))) return;
        try { await call(`parent/analytics/reports/${r.id}`, { method: "DELETE" }); AN.meta.reports = AN.meta.reports.filter(x => x !== r);
          if (AN.loaded && AN.loaded.id === r.id) AN.loaded = null; drawMine(); AN.drawActions && AN.drawActions(); } catch {}
      } }, "🗑️"))) : [h("p.small.muted", T("No saved reports yet – build one below and save it."))]));
    const st = mineFold.querySelector(".set-status");
    if (st) st.textContent = items.length ? I18N.tr(T("{0} saved")).replace("{0}", items.length) : anTr(T("None yet"));
  };
  AN.drawMine = drawMine;
  const tplFold = setFold("an.tpl", "📋 " + anTr(T("Templates")), tplBox);
  tplFold.querySelector(".set-status").textContent = I18N.tr(T("{0} templates")).replace("{0}", AN.meta.templates.length);
  tplBox.querySelector("h2").classList.add("fold-title");
  const mineFold = setFold("an.mine", "⭐ " + anTr(T("My reports")), mineBox);
  mineBox.querySelector("h2").classList.add("fold-title");
  root.append(tplFold, mineFold, anBuilder());
  drawMine();
}

function anLoad(spec, loaded) {
  AN.spec = { columns: [], rows: [], group: [], data: [], range: "30d", profiles: [], chart: "bar", ...JSON.parse(JSON.stringify(spec)) };
  delete AN.spec.from; delete AN.spec.to;
  AN.loaded = loaded;
  AN.redraw && AN.redraw();
  const b = document.querySelector(".an-builder");
  if (b) b.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---------------------------------------------------------------- the ad-hoc report
function anBuilder() {
  const box = h("section.card.sec.an-builder", h("h2", T("Ad-hoc report")));
  const out = h("div.an-out"), viz = h("div.an-viz", { role: "radiogroup", "aria-label": T("Chart type") });
  const head = h("div.an-loaded"), body = h("div.an-bbody"), actions = h("div.row.an-actions");
  box.append(head, body, out, viz, actions);
  let timer = null, seq = 0;
  const run = () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const s = AN.spec, my = ++seq;
      if (!s.data.length) { out.replaceChildren(anEmpty("📥", T("Drag a measure into «Data» – or tap a measure and then «Data»."))); return; }
      out.classList.add("an-busy");
      try {
        const res = await call("parent/analytics/query", { method: "POST", body: s });
        if (my !== seq) return;
        AN.result = res;
        out.replaceChildren(anRender(res, s.chart, { height: 280 }));
      } catch { /* the toast says why */ }
      finally { out.classList.remove("an-busy"); }
    }, 220);
  };
  const changed = () => { draw(); run(); };
  const draw = () => {
    const s = AN.spec, ds = AN.meta.datasets[s.dataset];
    head.replaceChildren(AN.loaded ? h("div.small.muted", "▶ ", AN.loaded.kind === "r" ? C(AN.loaded.name) : h("span", AN.loaded.name)) : "");
    const source = h("select", { "aria-label": T("Data source"), onchange: e => {
      const nd = AN.meta.datasets[e.target.value], dims = new Set(nd.dims.map(d => d[0])), ms = new Set(nd.measures.map(m => m[0]));
      s.dataset = e.target.value;
      for (const z of ["columns", "rows", "group"]) s[z] = s[z].filter(d => dims.has(d));
      s.data = s.data.filter(m => ms.has(m));
      if (!s.data.length) s.data = [nd.measures[0][0]];
      AN.sel = null; changed();
    } }, ...Object.entries(AN_DATASETS).map(([k, [ic, n]]) => h("option", { value: k, selected: k === s.dataset }, ic + " " + anTr(n))));
    const used = new Set([...s.columns, ...s.rows, ...s.group, ...s.data]);
    const pal = (kind, items) => h("div.an-pal", { "aria-label": kind === "dim" ? T("Dimensions") : T("Measures") },
      ...items.map(k => anChip({ kind, key: k }, null, used.has(k))));
    const zone = (z, title, hint) => {
      const keys = z === "data" ? s.data : s[z];
      const el = h("div.an-zone", { "data-zone": z, tabindex: 0, role: "button", "aria-label": anTr(title),
        onclick: e => { if (e.target === el || e.target.closest(".an-zone-h, .an-zone-hint")) anPlace(z, keys.length); },
        onkeydown: e => { if ((e.key === "Enter" || e.key === " ") && e.target === el) { e.preventDefault(); anPlace(z, keys.length); } } },
        h("div.an-zone-h", anTr(title)),
        ...(keys.length ? keys.map((k, i) => anChip({ kind: z === "data" ? "measure" : "dim", key: k }, { zone: z, index: i })) : [h("div.an-zone-hint.small.muted", anTr(hint))]));
      return el;
    };
    const ranges = h("div.an-seg", { role: "radiogroup", "aria-label": T("Period") }, ...AN_RANGES.map(([k, n]) =>
      h("button" + (s.range === k ? ".on" : ""), { type: "button", role: "radio", "aria-checked": String(s.range === k), onclick: () => { s.range = k; changed(); } }, n)));
    const people = AN.meta.profiles;
    const who = h("div.an-seg.an-who", { "aria-label": T("Who") },
      h("button" + (!s.profiles.length ? ".on" : ""), { type: "button", "aria-pressed": String(!s.profiles.length), onclick: () => { s.profiles = []; changed(); } }, T("Everybody")),
      ...people.map(p => h("button" + (s.profiles.includes(p.id) ? ".on" : ""), { type: "button", "aria-pressed": String(s.profiles.includes(p.id)), onclick: () => {
        s.profiles = s.profiles.includes(p.id) ? s.profiles.filter(x => x !== p.id) : [...s.profiles, p.id];
        if (s.profiles.length === people.length) s.profiles = [];
        changed();
      } }, h("span.an-dot", { style: { background: p.color } }), C(p.name))));
    body.replaceChildren(
      h("label.field.an-source", h("span", T("Data source")), source),
      h("div.an-palwrap", h("div.small.muted.an-pal-h", T("Dimensions")), pal("dim", ds.dims.map(d => d[0])),
        h("div.small.muted.an-pal-h", T("Measures")), pal("measure", ds.measures.map(m => m[0]))),
      h("div.an-zones", zone("columns", T("Columns"), T("Series / colours")), zone("rows", T("Rows"), T("Categories / x-axis")),
        zone("data", T("Data"), T("Measures")), zone("group", T("Group"), T("One chart per value"))),
      h("div.an-filters", ranges, who));
    viz.replaceChildren(...AN_CHARTS.map(([k, n, d]) => h("button.an-vbtn" + (s.chart === k ? ".on" : ""), { type: "button", role: "radio",
      "aria-checked": String(s.chart === k), title: n, "aria-label": n, onclick: () => { s.chart = k; draw(); if (AN.result) out.replaceChildren(anRender(AN.result, k, { height: 280 })); else run(); } },
      anIcon(d), h("span.an-vname", n))));
    drawActions();
    document.body.classList.toggle("an-picking", !!AN.sel);
  };
  const drawActions = () => {
    const own = AN.loaded && AN.loaded.kind === "r" && AN.meta.reports.some(r => r.id === AN.loaded.id);
    actions.replaceChildren(
      own ? h("button.btn.small", { type: "button", onclick: async () => {
        try { const r = await call(`parent/analytics/reports/${AN.loaded.id}`, { method: "PUT", body: { spec: AN.spec } });
          AN.meta.reports = AN.meta.reports.map(x => x.id === r.id ? r : x); AN.drawMine(); toast(T("Saved"), "good"); } catch {}
      } }, "💾 ", T("Save changes")) : null,
      h("button.btn.small" + (own ? ".ghost" : ""), { type: "button", disabled: !AN.spec.data.length, onclick: async () => {
        const n = await promptDialog(T("Name of the report"), AN.loaded && AN.loaded.kind === "t" ? I18N.tr(AN.loaded.name) : "", { maxLength: 60 });
        if (n == null || !n.trim()) return;
        try { const r = await call("parent/analytics/reports", { method: "POST", body: { name: n, spec: AN.spec } });
          AN.meta.reports.push(r); AN.loaded = { kind: "r", id: r.id, name: r.name }; AN.drawMine(); draw(); toast(T("Saved under «My reports»"), "good");
          SET_OPEN.add("an.mine"); const f = document.querySelector('details.set-fold[data-set="an.mine"]'); if (f) f.open = true; } catch {}
      } }, "⭐ ", T("Save as my report")),
      h("button.btn.small.ghost", { type: "button", onclick: () => { AN.spec = { ...AN.spec, columns: [], rows: [], group: [], data: [] }; AN.loaded = null; AN.sel = null; changed(); } }, "↺ ", T("Start over")));
  };
  AN.drawActions = drawActions;
  AN.redraw = changed;
  AN.builderChanged = changed;
  changed();
  return box;
}

function anEmpty(icon, text) { return h("div.an-empty", h("div.an-empty-ic", icon), h("p.muted", T(text))); }

// a chip of the palette or of a zone: drag it (pointer events), or tap it and then a zone
function anChip(item, from, used = false) {
  const [ic, name] = item.kind === "dim" ? AN_DIMS[item.key] || ["", item.key] : ["🔢", anMeasureName(item.key)];
  const sel = AN.sel && AN.sel.item.key === item.key && (!!AN.sel.from === !!from);
  const el = h("span.an-chip" + (item.kind === "measure" ? ".an-m" : "") + (from ? ".in" : "") + (used && !from ? ".used" : "") + (sel ? ".sel" : ""),
    { role: "button", tabindex: 0, "aria-pressed": String(!!sel), "data-key": item.key,
      onkeydown: e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); tap(); } if ((e.key === "Delete" || e.key === "Backspace") && from) anRemove(from); } },
    h("span.an-chip-ic", ic), h("span", name),
    from ? h("button.an-x", { type: "button", title: T("Remove"), "aria-label": T("Remove"), onpointerdown: e => e.stopPropagation(), onclick: e => { e.stopPropagation(); anRemove(from); } }, "×") : null);
  const tap = () => {
    if (AN.sel && from && AN.sel.from !== undefined && !(AN.sel.from && AN.sel.from.zone === from.zone && AN.sel.from.index === from.index) && anAccepts(from.zone, AN.sel.item)) {
      anPlace(from.zone, from.index); return;           // a chip is chosen: tapping a chip in a zone puts it before that one
    }
    AN.sel = sel ? null : { item, from };
    AN.builderChanged && AN.builderChanged();
  };
  anDrag(el, {
    onTap: tap,
    ghost: () => { const g = el.cloneNode(true); g.classList.add("an-ghost"); return g; },
    onMove: (x, y) => anHover(x, y, item),
    onDrop: (x, y) => { const t = anTarget(x, y, item); anHover(-1, -1); if (t) anDrop(item, from, t.zone, t.index); else if (from) anRemove(from); },
    onCancel: () => anHover(-1, -1),
  });
  return el;
}

const anAccepts = (zone, item) => zone === "data" ? item.kind === "measure" : item.kind === "dim";
function anTarget(x, y, item) {
  const z = document.elementFromPoint(x, y)?.closest(".an-zone");
  if (!z || !anAccepts(z.dataset.zone, item)) return null;
  const chips = [...z.querySelectorAll(".an-chip.in:not(.an-dragging)")];
  let index = chips.length;
  for (let i = 0; i < chips.length; i++) { const r = chips[i].getBoundingClientRect(); if (y < r.top + r.height / 2 && y < r.bottom || (y <= r.bottom && x < r.left + r.width / 2)) { index = i; break; } }
  const self = z.querySelector(".an-chip.in.an-dragging");
  if (self) { const si = [...z.querySelectorAll(".an-chip.in")].indexOf(self); if (si >= 0 && si < index) index += 1; }
  return { zone: z.dataset.zone, index, el: z };
}
function anHover(x, y, item) {
  document.querySelectorAll(".an-zone.over, .an-zone.no").forEach(z => z.classList.remove("over", "no"));
  if (x < 0) return;
  const z = document.elementFromPoint(x, y)?.closest(".an-zone");
  if (z) z.classList.add(anAccepts(z.dataset.zone, item) ? "over" : "no");
}
function anRemove(from) {
  const s = AN.spec, list = from.zone === "data" ? s.data : s[from.zone];
  list.splice(from.index, 1); AN.sel = null; AN.builderChanged();
}
function anPlace(zone, index) {
  if (!AN.sel) return;
  const { item, from } = AN.sel;
  if (!anAccepts(zone, item)) { toast(zone === "data" ? T("Only measures go into «Data»") : T("Measures go into «Data»"), "bad"); return; }
  anDrop(item, from, zone, index);
}
function anDrop(item, from, zone, index) {
  const s = AN.spec, list = z => z === "data" ? s.data : s[z];
  if (from) { const l = list(from.zone); l.splice(from.index, 1); if (from.zone === zone && from.index < index) index -= 1; }
  else for (const z of ["columns", "rows", "group", "data"]) { const l = list(z), i = l.indexOf(item.key); if (i >= 0) { l.splice(i, 1); if (z === zone && i < index) index -= 1; } }
  const l = list(zone);
  const dims = s.columns.length + s.rows.length + s.group.length;
  if (item.kind === "dim" && dims >= AN.meta.limits.dims) { toast(T("At most 3 dimensions"), "bad"); AN.builderChanged(); return; }
  if (item.kind === "measure" && s.data.length >= AN.meta.limits.measures) { toast(T("At most 4 different measures"), "bad"); AN.builderChanged(); return; }
  l.splice(Math.max(0, Math.min(index, l.length)), 0, item.key);
  AN.sel = null;
  AN.builderChanged();
}

/** Drag with pointer events (mouse, pen and finger): a ghost follows the pointer after 6 px; less is a tap. */
function anDrag(el, { onTap, onStart, onMove, onDrop, onCancel, ghost, handle = el, threshold = 6 }) {
  handle.style.touchAction = "none";
  handle.addEventListener("pointerdown", e => {
    if (e.button > 0 || e.target.closest(".an-x, .an-tbtn")) return;
    if (e.pointerType === "mouse") e.preventDefault();               // no text selection while dragging
    const x0 = e.clientX, y0 = e.clientY, id = e.pointerId;
    let g = null, dragging = false, dx = 0, dy = 0;
    try { handle.setPointerCapture(id); } catch {}
    const move = ev => {
      if (ev.pointerId !== id) return;
      if (!dragging && Math.hypot(ev.clientX - x0, ev.clientY - y0) > threshold) {
        dragging = true;
        const r = el.getBoundingClientRect(); dx = x0 - r.left; dy = y0 - r.top;
        if (ghost) { g = ghost(); g.style.width = r.width + "px"; document.body.append(g); }
        el.classList.add("an-dragging"); document.body.classList.add("an-drag-on");
        onStart && onStart();
      }
      if (dragging) {
        ev.preventDefault();
        if (g) g.style.transform = `translate(${ev.clientX - dx}px, ${ev.clientY - dy}px)`;
        onMove && onMove(ev.clientX, ev.clientY, ev.clientX - x0, ev.clientY - y0);
      }
    };
    const end = ev => {
      if (ev.pointerId !== id) return;
      handle.removeEventListener("pointermove", move); handle.removeEventListener("pointerup", end); handle.removeEventListener("pointercancel", end);
      el.classList.remove("an-dragging"); document.body.classList.remove("an-drag-on");
      if (g) g.remove();
      if (!dragging) { if (ev.type === "pointerup") onTap && onTap(); return; }
      if (ev.type === "pointercancel") onCancel && onCancel(); else onDrop && onDrop(ev.clientX, ev.clientY, ev.clientX - x0, ev.clientY - y0);
    };
    handle.addEventListener("pointermove", move); handle.addEventListener("pointerup", end); handle.addEventListener("pointercancel", end);
  });
}
document.addEventListener("keydown", e => { if (e.key === "Escape" && AN.sel) { AN.sel = null; AN.builderChanged && AN.builderChanged(); } });

// ================================================================ rendering: table, pivot, charts
function anVal(m, v) {
  if (v == null || v === "") return "–";
  const u = m.unit === "%" ? " %" : m.unit === "min" ? " min" : m.unit === "h" ? " h" : "";
  return fmt(v, Math.abs(v) < 10 && !Number.isInteger(v) ? 2 : 1) + u;
}
function anIsoWeek(s) {
  const d = new Date(s + "T12:00:00"); d.setDate(d.getDate() + 3 - ((d.getDay() + 6) % 7));
  const w1 = new Date(d.getFullYear(), 0, 4);
  return 1 + Math.round(((d - w1) / 864e5 - 3 + ((w1.getDay() + 6) % 7)) / 7);
}
function anLabel(dim, v) {
  const s = String(v), loc = I18N.locale;
  try {
    switch (dim.kind) {
      case "profile": return dim.labels[s] || "?";
      case "day": return new Date(s + "T12:00:00").toLocaleDateString(loc, { day: "numeric", month: "short" });
      case "week": return I18N.tr(T("Wk {0}")).replace("{0}", anIsoWeek(s));
      case "month": return new Date(s + "-01T12:00:00").toLocaleDateString(loc, { month: "short", year: "2-digit" });
      case "weekday": return new Date(2024, 0, 1 + Number(v)).toLocaleDateString(loc, { weekday: "short" });
      case "year": return s;
      case "reward_kind": return anTr(KIND_NAMES[s] || s);
      case "exercise": return anTr(EXERCISES[s] || (s === "other" ? T("Other") : s));
      default: return anTr((AN_VALUES[dim.kind] || {})[s] || dim.labels[s] || s);
    }
  } catch { return s; }
}

function anModel(res) {
  const sp = res.spec, g = sp.group.length, r = sp.rows.length, c = sp.columns.length;
  const key = t => JSON.stringify(t);
  const idx = (o, v) => { const i = o.indexOf(String(v)); return i < 0 ? 1e9 : i; };
  const cmp = (a, x, y) => {
    for (let i = 0; i < x.length; i++) {
      const d = res.dims[a + i];
      const k = d.order ? idx(d.order, x[i]) - idx(d.order, y[i]) : typeof x[i] === "number" && typeof y[i] === "number" ? x[i] - y[i]
        : String(x[i]).localeCompare(String(y[i]), undefined, { numeric: true });
      if (k) return k;
    }
    return 0;
  };
  const uniq = (a, n) => { const m = new Map(); for (const row of res.rows) { const t = row.slice(a, a + n); m.set(key(t), t); } return [...m.values()].sort((x, y) => cmp(a, x, y)); };
  const label = (t, a) => t.map((v, i) => anLabel(res.dims[a + i], v)).join(" · ");
  const cells = new Map();
  for (const row of res.rows) cells.set(key(row.slice(0, g)) + "|" + key(row.slice(g, g + r)) + "|" + key(row.slice(g + r, g + r + c)), row.slice(g + r + c));
  return {
    groups: uniq(0, g).map(t => ({ k: key(t), label: g ? label(t, 0) : "" })),
    cats: uniq(g, r).map(t => ({ k: key(t), label: r ? label(t, g) : anTr(T("Sum")) })),
    series: uniq(g + r, c).map(t => ({ k: key(t), label: c ? label(t, g + r) : "" })),
    get: (gk, ck, sk, mi) => { const v = cells.get(gk + "|" + ck + "|" + sk); return v ? v[mi] : null; },
    measures: res.measures, rCount: r, cCount: c, spec: sp,
  };
}

/** The result as the chosen visualisation: an element that draws itself at the width it gets (and again on resize). */
function anRender(res, chart, { height = 280 } = {}) {
  const wrap = h("div.an-report");
  if (!res.rows.length || res.rows.every(r => r.slice(res.dims.length).every(v => !v))) {
    wrap.append(anEmpty("🫙", T("No data for this period – choose a longer period or other people.")));
    return wrap;
  }
  if (res.truncated) wrap.append(h("p.small.warn-text", "⚠️ ", I18N.tr(T("Only the first {0} rows are shown – choose fewer dimensions or a shorter period.")).replace("{0}", fmt(res.rows.length))));
  if (chart === "table") { wrap.append(anTable(res)); return wrap; }
  const M = anModel(res);
  if (chart === "pivot") { for (const gr of M.groups) wrap.append(...[gr.label ? h("h3.an-gtitle", h("span", { translate: "no" }, gr.label)) : null, anPivot(M, gr)].filter(Boolean)); return wrap; }
  // charts: one panel per group value and measure (one axis per chart, never two scales)
  const panels = [];
  for (const gr of M.groups) M.measures.forEach((m, mi) => panels.push({ gr, m, mi }));
  const many = panels.length > 1;
  const shown = panels.slice(0, 12);
  for (const p of shown) {
    const title = [p.gr.label, many && M.measures.length > 1 ? anTr(anMeasureName(p.m.key)) : null].filter(Boolean).join(" · ");
    const box = h("div.an-panel", title ? h("div.an-ptitle", { translate: "no" }, title) : null);
    const c = anChart(M, p.gr, p.m, p.mi, chart, many ? Math.max(170, height * .75) : height);
    box.append(c);
    wrap.append(box);
  }
  if (panels.length > shown.length) wrap.append(h("p.small.muted", I18N.tr(T("{0} more charts are not shown – use a filter or the table.")).replace("{0}", panels.length - shown.length)));
  wrap.classList.toggle("an-multi", many);
  return wrap;
}

function anTable(res) {
  const sp = res.spec, dims = [...sp.group, ...sp.rows, ...sp.columns];
  const rows = res.rows.slice(0, 500);
  const t = h("table.an-table", h("thead", h("tr", ...dims.map(d => h("th", anDimName(d))), ...res.measures.map(m => h("th.num", anMeasureName(m.key))))),
    h("tbody", ...rows.map(r => h("tr", ...dims.map((_, i) => h("td", { translate: "no" }, anLabel(res.dims[i], r[i]))),
      ...res.measures.map((m, j) => h("td.num", { translate: "no" }, anVal(m, r[dims.length + j])))))));
  return h("div.an-tscroll", t, res.rows.length > 500 ? h("p.small.muted", I18N.tr(T("Only the first {0} rows are shown – choose fewer dimensions or a shorter period.")).replace("{0}", "500")) : null);
}

function anPivot(M, gr) {
  const cats = M.cats.filter(c => M.series.some(s => M.measures.some((m, mi) => M.get(gr.k, c.k, s.k, mi) != null)));
  const cols = [];
  for (const s of M.series) M.measures.forEach((m, mi) => cols.push({ s, m, mi }));
  const add = m => !AN_NOT_ADDITIVE.has(m.key);
  const head2 = M.cCount && M.measures.length > 1;
  const thead = h("thead",
    h("tr", h("th.an-corner", { rowspan: head2 ? 2 : 1 }, M.rCount ? anPivotCorner(M.spec) : ""),
      ...(head2 ? M.series.map(s => h("th.center", { colspan: M.measures.length, translate: "no" }, s.label))
        : cols.map(c => h("th.num", { translate: "no" }, M.cCount ? c.s.label : anTr(anMeasureName(c.m.key))))),
      M.cCount ? h("th.num.an-tot", { rowspan: head2 ? 2 : 1 }, T("Sum")) : null),
    head2 ? h("tr", ...cols.map(c => h("th.num", anMeasureName(c.m.key)))) : null);
  const rowTotal = c => M.measures.map((m, mi) => add(m) ? M.series.reduce((a, s) => a + (M.get(gr.k, c.k, s.k, mi) || 0), 0) : null);
  const tbody = h("tbody", ...cats.map(c => h("tr", h("th", { translate: "no" }, c.label),
    ...cols.map(x => h("td.num", { translate: "no" }, anVal(x.m, M.get(gr.k, c.k, x.s.k, x.mi)))),
    M.cCount ? h("td.num.an-tot", { translate: "no" }, rowTotal(c).map((v, i) => anVal(M.measures[i], v)).join(" / ")) : null)));
  const foot = cats.length > 1 ? h("tfoot", h("tr", h("th", T("Sum")),
    ...cols.map(x => h("td.num", { translate: "no" }, add(x.m) ? anVal(x.m, cats.reduce((a, c) => a + (M.get(gr.k, c.k, x.s.k, x.mi) || 0), 0)) : "–")),
    M.cCount ? h("td.num.an-tot", { translate: "no" }, M.measures.map((m, mi) => add(m) ? anVal(m, cats.reduce((a, c) => a + rowTotal(c)[mi], 0)) : "–").join(" / ")) : null)) : null;
  return h("div.an-tscroll", h("table.an-table.an-pivot", thead, tbody, foot));
}
function anPivotCorner(sp) { return sp.rows.map(anDimName).map(anTr).join(" · ") + (sp.columns.length ? " ╲ " + sp.columns.map(anDimName).map(anTr).join(" · ") : ""); }

function anNice(lo, hi, n = 4) {
  if (lo === hi) { hi = lo + 1; lo = Math.min(0, lo); }
  const span = hi - lo, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / mag;
  const step = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * mag;
  const a = Math.floor(lo / step) * step, b = Math.ceil(hi / step) * step, ticks = [];
  for (let v = a; v <= b + step / 2; v += step) ticks.push(+v.toFixed(10));
  return { lo: a, hi: b, ticks };
}

/** One chart (bar / stacked / 100 % / line / area / donut) of one measure, drawn as SVG at the width of its box. */
function anChart(M, gr, m, mi, type, height) {
  const box = h("div.an-chart", { style: { height: height + "px" } });
  const tip = h("div.an-tip", { role: "status", hidden: true });
  const legend = h("div.an-legend");
  const outer = h("div.an-chartbox", box, legend);
  box.append(tip);
  const cats = M.cats.filter(c => M.series.some(s => M.get(gr.k, c.k, s.k, mi) != null));
  let series = M.series.map((s, i) => ({ ...s, i, label: s.label || anTr(anMeasureName(m.key)) }));
  const val = (c, s) => s.other ? s.other.reduce((a, x) => a + (M.get(gr.k, c.k, x.k, mi) || 0), 0) : M.get(gr.k, c.k, s.k, mi) || 0;
  if (series.length > 8) {          // never a 9th colour: the smallest series become «Other»
    const tot = s => cats.reduce((a, c) => a + Math.abs(M.get(gr.k, c.k, s.k, mi) || 0), 0);
    const keep = new Set([...series].sort((a, b) => tot(b) - tot(a)).slice(0, 7).map(s => s.k));
    series = [...series.filter(s => keep.has(s.k)), { k: "__other", label: anTr(T("Other")), other: series.filter(s => !keep.has(s.k)) }];
  }
  series.forEach((s, i) => { s.color = `var(--an-s${i + 1})`; });
  const pie = type === "pie";
  if (pie) {
    // slices: the categories (rows), else the series; the rest added up
    let slices = M.rCount ? cats.map(c => ({ label: c.label, v: series.reduce((a, s) => a + val(c, s), 0) })) : series.map(s => ({ label: s.label, v: cats.reduce((a, c) => a + val(c, s), 0) }));
    slices = slices.filter(x => x.v > 0);
    if (slices.length > 8) { const sorted = [...slices].sort((a, b) => b.v - a.v); const keep = new Set(sorted.slice(0, 7)); slices = [...slices.filter(x => keep.has(x)), { label: anTr(T("Other")), v: sorted.slice(7).reduce((a, x) => a + x.v, 0) }]; }
    slices.forEach((x, i) => { x.color = `var(--an-s${i + 1})`; });
    const total = slices.reduce((a, x) => a + x.v, 0);
    legend.append(...slices.map(x => h("span.an-li", h("span.an-sw", { style: { background: x.color } }), h("span", { translate: "no" }, x.label), h("span.muted", { translate: "no" }, " " + fmt(total ? x.v / total * 100 : 0, 0) + " %"))));
    box._draw = W => {
      box.querySelector("svg")?.remove();
      const H = height, R = Math.max(40, Math.min(W, H) / 2 - 8), r0 = R * .6, cx = W / 2, cy = H / 2;
      const svg = anSvg("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": anTr(anMeasureName(m.key)), translate: "no" });
      if (!total) { box.prepend(svg); return; }
      let a0 = -Math.PI / 2;
      for (const x of slices) {
        const a1 = a0 + (x.v / total) * Math.PI * 2, big = a1 - a0 > Math.PI ? 1 : 0;
        const p = (rr, a) => `${cx + rr * Math.cos(a)} ${cy + rr * Math.sin(a)}`;
        const d = slices.length === 1 ? `M${cx - R} ${cy}a${R} ${R} 0 1 0 ${2 * R} 0a${R} ${R} 0 1 0 ${-2 * R} 0M${cx - r0} ${cy}a${r0} ${r0} 0 1 1 ${2 * r0} 0a${r0} ${r0} 0 1 1 ${-2 * r0} 0`
          : `M${p(R, a0)}A${R} ${R} 0 ${big} 1 ${p(R, a1)}L${p(r0, a1)}A${r0} ${r0} 0 ${big} 0 ${p(r0, a0)}Z`;
        const path = anSvg("path", { d, fill: x.color, stroke: "var(--card)", "stroke-width": 2, "fill-rule": "evenodd", class: "an-mark", tabindex: 0 });
        const show = e => anTip(box, tip, e, x.label, [[x.color, fmt(x.v, 1) + " · " + fmt(x.v / total * 100, 0) + " %", ""]]);
        path.addEventListener("pointermove", show); path.addEventListener("pointerdown", show); path.addEventListener("focus", show);
        path.addEventListener("pointerleave", () => { tip.hidden = true; }); path.addEventListener("blur", () => { tip.hidden = true; });
        svg.append(path);
        a0 = a1;
      }
      const t1 = anSvg("text", { x: cx, y: cy - 2, "text-anchor": "middle", class: "an-center" }); t1.textContent = anVal(m, total);
      const t2 = anSvg("text", { x: cx, y: cy + 16, "text-anchor": "middle", class: "an-axis" }); t2.textContent = anTr(T("Sum"));
      if (!AN_NOT_ADDITIVE.has(m.key)) svg.append(t1, t2);
      box.prepend(svg);
    };
  } else {
    if (series.length > 1) legend.append(...series.map(s => h("span.an-li", type === "line" ? h("span.an-swl", { style: { background: s.color } }) : h("span.an-sw", { style: { background: s.color } }), h("span", { translate: "no" }, s.label))));
    const stacked = type === "stacked" || type === "stacked100" || type === "area", pct = type === "stacked100";
    const vals = cats.map(c => series.map(s => val(c, s)));
    const plotV = vals.map(row => { if (pct) { const t = row.reduce((a, v) => a + Math.abs(v), 0) || 1; return row.map(v => Math.abs(v) / t * 100); } return type === "area" ? row.map(v => Math.max(0, v)) : row; });
    let lo = 0, hi = 0;
    for (const row of plotV) {
      if (stacked) { hi = Math.max(hi, row.reduce((a, v) => a + Math.max(0, v), 0)); lo = Math.min(lo, row.reduce((a, v) => a + Math.min(0, v), 0)); }
      else for (const v of row) { hi = Math.max(hi, v); lo = Math.min(lo, v); }
    }
    if (pct) { lo = 0; hi = 100; }
    if (type === "line" && lo > 0) lo = 0;
    const sc = anNice(lo, hi, height < 200 ? 3 : 4);
    const unit = pct ? { unit: "%" } : m;
    box._draw = W => {
      box.querySelector("svg")?.remove();
      const H = height, labW = Math.min(64, 12 + Math.max(...sc.ticks.map(t => anVal(unit, t).length)) * 6.6);
      const L = labW, Rm = 8, Tm = 8, B = 26, pw = Math.max(20, W - L - Rm), ph = Math.max(20, H - Tm - B);
      const y = v => Tm + ph - (v - sc.lo) / (sc.hi - sc.lo) * ph;
      const svg = anSvg("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": anTr(anMeasureName(m.key)), translate: "no" });
      for (const t of sc.ticks) {
        svg.append(anSvg("line", { x1: L, x2: W - Rm, y1: y(t), y2: y(t), class: t === 0 ? "an-zero" : "an-gl" }));
        const tx = anSvg("text", { x: L - 6, y: y(t) + 4, "text-anchor": "end", class: "an-axis" }); tx.textContent = anVal(unit, t); svg.append(tx);
      }
      const n = Math.max(1, cats.length), band = pw / n, line = type === "line" || type === "area";
      const cx = i => L + band * i + band / 2;
      // x labels: as many as fit without touching
      const maxChars = Math.max(...cats.map(c => c.label.length), 1), each = Math.max(1, Math.ceil((maxChars * 6.4 + 8) / band));
      cats.forEach((c, i) => {
        if (i % each) return;
        const tx = anSvg("text", { x: cx(i), y: H - 8, "text-anchor": "middle", class: "an-axis" });
        const room = Math.floor(band * each / 6.4);
        tx.textContent = c.label.length > room && room > 3 ? c.label.slice(0, room - 1) + "…" : c.label;
        svg.append(tx);
      });
      const hl = anSvg("rect", { class: "an-band", x: 0, y: Tm, width: 0, height: ph, visibility: "hidden" });
      svg.append(hl);
      if (!line) {
        const gw = band * (n > 20 ? .86 : .72), bw = stacked ? gw : gw / series.length;
        cats.forEach((c, i) => {
          let up = 0, dn = 0;
          series.forEach((s, j) => {
            const v = plotV[i][j]; if (!v) return;
            let y0, y1;
            if (stacked) { if (v >= 0) { y0 = up; y1 = up + v; up = y1; } else { y0 = dn; y1 = dn + v; dn = y1; } } else { y0 = 0; y1 = v; }
            const x = stacked ? cx(i) - gw / 2 : cx(i) - gw / 2 + j * bw;
            const top = Math.min(y(y0), y(y1)), hh = Math.max(1, Math.abs(y(y0) - y(y1)));
            const outerEnd = !stacked || (v >= 0 ? up === y1 && j === series.map((_, k) => plotV[i][k] > 0 ? k : -1).reduce((a, b) => Math.max(a, b), -1) : dn === y1 && j === series.map((_, k) => plotV[i][k] < 0 ? k : -1).reduce((a, b) => Math.max(a, b), -1));
            svg.append(anSvg("path", { d: anBarPath(x + .5, top, Math.max(1, bw - 1), hh, outerEnd ? Math.min(4, bw / 2 - .5, hh) : 0, v >= 0), fill: s.color, stroke: "var(--card)", "stroke-width": series.length > 1 || stacked ? 1 : 0, class: "an-mark" }));
          });
        });
      } else {
        const pts = j => cats.map((c, i) => { let base = 0; if (type === "area") for (let k = 0; k < j; k++) base += plotV[i][k]; return [cx(i), base, base + plotV[i][j]]; });
        series.forEach((s, j) => {
          const p = pts(j);
          if (type === "area") svg.append(anSvg("path", { d: "M" + p.map(q => `${q[0]} ${y(q[2])}`).join("L") + "L" + [...p].reverse().map(q => `${q[0]} ${y(q[1])}`).join("L") + "Z", fill: s.color, "fill-opacity": .78, stroke: "var(--card)", "stroke-width": 1 }));
          svg.append(anSvg("path", { d: "M" + p.map(q => `${q[0]} ${y(q[2])}`).join("L"), fill: "none", stroke: s.color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
          if (cats.length === 1) svg.append(anSvg("circle", { cx: p[0][0], cy: y(p[0][2]), r: 4, fill: s.color }));
        });
      }
      // one hit area per category (bigger than the marks): the tooltip lists every series there
      const dots = anSvg("g");
      svg.append(dots);
      cats.forEach((c, i) => {
        const hit = anSvg("rect", { x: L + band * i, y: Tm, width: band, height: ph, fill: "transparent", tabindex: 0, class: "an-hit", "aria-label": c.label });
        const show = e => {
          hl.setAttribute("x", line ? cx(i) - .75 : L + band * i); hl.setAttribute("width", line ? 1.5 : band); hl.setAttribute("visibility", "visible");
          hl.setAttribute("class", line ? "an-cross" : "an-band");
          dots.replaceChildren();
          if (line) series.forEach((s, j) => { let v = plotV[i][j]; if (type === "area") for (let k = 0; k < j; k++) v += plotV[i][k]; dots.append(anSvg("circle", { cx: cx(i), cy: y(v), r: 4.5, fill: s.color, stroke: "var(--card)", "stroke-width": 2 })); });
          const rows = series.map((s, j) => [s.color, pct ? fmt(plotV[i][j], 0) + " % · " + anVal(m, vals[i][j]) : anVal(m, vals[i][j]), series.length > 1 ? s.label : ""]).filter((_, j) => vals[i][j] || series.length === 1);
          if (stacked && series.length > 1 && !AN_NOT_ADDITIVE.has(m.key)) rows.push(["", anVal(m, vals[i].reduce((a, v) => a + v, 0)), anTr(T("Sum"))]);
          anTip(box, tip, e, c.label, rows, line ? "line" : "box");
        };
        hit.addEventListener("pointermove", show); hit.addEventListener("pointerdown", show); hit.addEventListener("focus", show);
        const hide = () => { tip.hidden = true; hl.setAttribute("visibility", "hidden"); dots.replaceChildren(); };
        hit.addEventListener("pointerleave", e => { if (e.pointerType === "mouse") hide(); }); hit.addEventListener("blur", hide);
        svg.append(hit);
      });
      box.prepend(svg);
    };
  }
  // drawn when it has its width, and again when the width changes
  let lastW = 0;
  const ro = new ResizeObserver(() => { const W = Math.floor(box.clientWidth); if (W > 0 && W !== lastW) { lastW = W; box._draw(W); } });
  ro.observe(box);
  return outer;
}
function anBarPath(x, y, w, h, r, up) {
  if (!r) return `M${x} ${y}h${w}v${h}h${-w}Z`;
  return up ? `M${x} ${y + h}V${y + r}Q${x} ${y} ${x + r} ${y}H${x + w - r}Q${x + w} ${y} ${x + w} ${y + r}V${y + h}Z`
    : `M${x} ${y}V${y + h - r}Q${x} ${y + h} ${x + r} ${y + h}H${x + w - r}Q${x + w} ${y + h} ${x + w} ${y + h - r}V${y}Z`;
}
// the tooltip: the value leads, the name follows; keyed with a short line of the series colour (textContent only)
function anTip(box, tip, e, title, rows, kind = "box") {
  tip.replaceChildren(h("div.an-tip-h", { translate: "no" }, title), ...rows.map(([color, v, name]) => h("div.an-tip-r",
    color ? h("span.an-swl", { style: { background: color } }) : h("span.an-swl.none"), h("strong", { translate: "no" }, v), name ? h("span.muted", { translate: "no" }, name) : null)));
  tip.hidden = false;
  const r = box.getBoundingClientRect();
  let x = (e.clientX != null && e.type !== "focus" ? e.clientX : (e.target.getBoundingClientRect().left + e.target.getBoundingClientRect().width / 2)) - r.left;
  let y = (e.clientY != null && e.type !== "focus" ? e.clientY : e.target.getBoundingClientRect().top + 20) - r.top;
  const tw = tip.offsetWidth, th = tip.offsetHeight;
  x = x + 14 + tw > r.width ? Math.max(0, x - 14 - tw) : x + 14;
  y = Math.max(0, Math.min(r.height - th, y - th / 2));
  tip.style.transform = `translate(${x}px, ${y}px)`;
}
document.addEventListener("pointerdown", e => { if (!e.target.closest(".an-chart")) document.querySelectorAll(".an-tip").forEach(t => { t.hidden = true; }); }, true);

// ================================================================ Dashboards tab
const AN_PERIODS = [["day", T("Day")], ["week", T("Week")], ["month", T("Month")], ["year", T("Year")], ["r12", T("Rolling 12 months")]];
const anISO = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const anDate = s => new Date(s + "T12:00:00");
const anAddDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const anAddMonths = (d, n) => new Date(d.getFullYear(), d.getMonth() + n, 1, 12);
function anFirstDay() {
  try { const l = new Intl.Locale(I18N.locale); const w = l.getWeekInfo ? l.getWeekInfo() : l.weekInfo; if (w && w.firstDay) return w.firstDay % 7; } catch {}
  return /^en-US/.test(I18N.locale) ? 0 : 1;
}
/** The period of a type around a day: [from, to] (dates). */
function anPeriodAt(type, d) {
  d = new Date(d.getFullYear(), d.getMonth(), d.getDate(), 12);
  if (type === "day") return [d, d];
  if (type === "week") { const s = anAddDays(d, -((d.getDay() - anFirstDay() + 7) % 7)); return [s, anAddDays(s, 6)]; }
  if (type === "month") return [new Date(d.getFullYear(), d.getMonth(), 1, 12), new Date(d.getFullYear(), d.getMonth() + 1, 0, 12)];
  if (type === "quarter") { const q = Math.floor(d.getMonth() / 3) * 3; return [new Date(d.getFullYear(), q, 1, 12), new Date(d.getFullYear(), q + 3, 0, 12)]; }
  if (type === "year") return [new Date(d.getFullYear(), 0, 1, 12), new Date(d.getFullYear(), 11, 31, 12)];
  if (type === "r12") return [anAddMonths(d, -11), new Date(d.getFullYear(), d.getMonth() + 1, 0, 12)];
  return [d, d];
}
function anPeriod(p) {
  if (p && p.from && p.to) return [anDate(p.from), anDate(p.to)];
  return anPeriodAt(p && p.type || "month", new Date());
}
function anStep(p, dir) {
  const [a, b] = anPeriod(p);
  if (p.type === "custom") { const n = Math.round((b - a) / 864e5) + 1; return { type: "custom", from: anISO(anAddDays(a, dir * n)), to: anISO(anAddDays(b, dir * n)) }; }
  const months = { month: 1, quarter: 3, year: 12, r12: 12 }[p.type];
  const at = months ? anAddMonths(p.type === "r12" ? b : a, dir * months) : anAddDays(a, dir * (p.type === "week" ? 7 : 1));
  const [f, t] = anPeriodAt(p.type, p.type === "r12" ? new Date(at.getFullYear(), at.getMonth(), 1, 12) : at);
  return { type: p.type, from: anISO(f), to: anISO(t) };
}
function anNow(p) {
  if (p.type === "custom") { const [a, b] = anPeriod(p); const n = Math.round((b - a) / 864e5); const t = new Date(); return { type: "custom", from: anISO(anAddDays(t, -n)), to: anISO(t) }; }
  return { type: p.type };
}
/** The title of a period in the user's language: «November» / «2026», «16.–22. Nov.», «Dez.–Nov.» / «2025–2026». */
function anPeriodTitle(p) {
  const [a, b] = anPeriod(p), loc = I18N.locale, ya = a.getFullYear(), yb = b.getFullYear();
  const range = (o) => { try { return new Intl.DateTimeFormat(loc, o).formatRange(a, b); } catch { return a.toLocaleDateString(loc, o) + " – " + b.toLocaleDateString(loc, o); } };
  const sub = ya === yb ? String(ya) : ya + "–" + yb;
  switch (p.type) {
    case "day": return [a.toLocaleDateString(loc, { weekday: "short", day: "numeric", month: "short" }), String(ya)];
    case "week": return [range({ day: "numeric", month: "short" }), sub];
    case "month": return [a.toLocaleDateString(loc, { month: "long" }), String(ya)];
    case "quarter": return [range({ month: "short" }), String(ya)];
    case "year": return [String(ya), ""];
    case "r12": return [range({ month: "short" }), sub];
    default: return [anISO(a) === anISO(b) ? a.toLocaleDateString(loc, { day: "numeric", month: "short" }) : range({ day: "numeric", month: "short" }), sub];
  }
}

function anDashPane(root) {
  const ds = AN.meta.dashboards;
  let cur = ds.find(d => d.id === anStore.get("dash", "std")) || ds[0];
  const card = h("section.card.sec.an-dash");
  const tl = h("div.an-tl"), pal = h("div.an-dpal"), grid = h("div.an-grid");
  root.append(card);
  let saveT = null;
  const save = (body, after) => { clearTimeout(saveT); saveT = setTimeout(async () => {
    try {
      const d = await call(`parent/analytics/dashboards/${cur.id}`, { method: "PUT", body });
      // the tiles stay the same objects (the open tiles hold them): only their new ids are taken over
      if (d.tiles.length === cur.tiles.length) d.tiles.forEach((x, i) => { cur.tiles[i].id = x.id; });
      delete d.tiles; Object.assign(cur, d); after && after();
    } catch {}
  }, body.tiles ? 350 : 0); };
  const draw = () => {
    const pick = h("select.an-dsel", { "aria-label": T("Dashboard"), onchange: e => { cur = ds.find(d => d.id === e.target.value); anStore.set("dash", cur.id); AN.edit = false; draw(); } },
      ...ds.map(d => h("option", { value: d.id, selected: d === cur, translate: d.standard ? null : "no" }, d.standard ? anTr(d.name) : d.name)));
    const more = h("button.icon-btn", { type: "button", title: T("More"), "aria-label": T("More"), onclick: () => anMenu(more, [
      [T("New dashboard"), "＋", async () => { const n = await promptDialog(T("Name of the dashboard"), "", { maxLength: 60 }); if (n == null || !n.trim()) return;
        try { const d = await call("parent/analytics/dashboards", { method: "POST", body: { name: n } }); ds.push(d); cur = d; anStore.set("dash", d.id); AN.edit = true; draw(); } catch {} }],
      [T("Rename"), "✏️", async () => { const n = await promptDialog(T("Name of the dashboard"), cur.standard ? anTr(cur.name) : cur.name, { maxLength: 60 }); if (n == null || !n.trim()) return;
        try { Object.assign(cur, await call(`parent/analytics/dashboards/${cur.id}`, { method: "PUT", body: { name: n } })); cur.standard = false; draw(); } catch {} }],
      cur.id !== "std" ? [T("Delete"), "🗑️", async () => { if (!await confirmDialog(I18N.tr(T("Delete the dashboard «{0}»?")).replace("{0}", cur.name))) return;
        try { await call(`parent/analytics/dashboards/${cur.id}`, { method: "DELETE" }); ds.splice(ds.indexOf(cur), 1); cur = ds[0]; anStore.set("dash", cur.id); AN.edit = false; draw(); } catch {} }] : null,
    ].filter(Boolean)) }, "⋯");
    card.replaceChildren(
      h("h2", T("Dashboards")),
      h("div.an-dbar", pick,
        h("button.btn.small" + (AN.edit ? "" : ".ghost"), { type: "button", "aria-pressed": String(AN.edit), onclick: () => { AN.edit = !AN.edit; draw(); } }, AN.edit ? "✓ " : "✏️ ", AN.edit ? T("Done") : T("Edit")), more),
      tl, AN.edit ? pal : null, grid);
    drawTimeline(); drawPal(); drawGrid();
  };
  const setPeriod = p => { cur.period = p; drawTimeline(); drawGrid(); save({ period: p }); };
  const drawTimeline = () => {
    const p = cur.period || { type: "month" };
    const [t1, t2] = anPeriodTitle(p);
    const open = () => anPicker(tl, p, setPeriod);
    const kebab = h("button.icon-btn.an-tl-more", { type: "button", title: T("Period type"), "aria-label": T("Period type"), onclick: () => anMenu(kebab, [
      ...AN_PERIODS.map(([k, n]) => [n, p.type === k ? "✓" : "", () => setPeriod({ type: k })]),
      [T("Custom range…"), p.type === "custom" ? "✓" : "📅", open]]) }, "⋮");
    tl.replaceChildren(
      h("button.icon-btn.an-tl-cal", { type: "button", title: T("Choose a period"), "aria-label": T("Choose a period"), onclick: open }, anIcon("M4 6h16v14H4zM4 10h16M8 3v5M16 3v5")),
      h("button.an-tl-title", { type: "button", onclick: open, "aria-label": T("Choose a period") }, h("strong", { translate: "no" }, t1), t2 ? h("span.small.muted", { translate: "no" }, t2) : null),
      h("button.btn.small.ghost.an-tl-now", { type: "button", onclick: () => setPeriod(anNow(p)) }, T("Now")),
      h("button.icon-btn", { type: "button", title: T("Back"), "aria-label": T("Back"), onclick: () => setPeriod(anStep(p, -1)) }, "◀"),
      h("button.icon-btn", { type: "button", title: T("Next"), "aria-label": T("Next"), onclick: () => setPeriod(anStep(p, 1)) }, "▶"),
      kebab);
  };
  const refOf = ref => {
    if (ref.startsWith("t:")) { const t = AN.meta.templates.find(x => x.key === ref.slice(2)); return t && { spec: t.spec, title: anTr(t.title), icon: t.icon }; }
    const r = AN.meta.reports.find(x => x.id === ref.slice(2)); return r && { spec: r.spec, title: r.name, icon: "⭐", own: true };
  };
  const insertTile = (ref, at = cur.tiles.length) => { cur.tiles.splice(at, 0, { id: "", ref, w: 2, h: "m", title: "" }); drawGrid(); save({ tiles: cur.tiles }); };
  const drawPal = () => {
    const chipOf = (ref, ic, name, own) => {
      const el = h("span.an-chip.an-rchip", { role: "button", tabindex: 0, onkeydown: e => { if (e.key === "Enter") insertTile(ref); } }, h("span.an-chip-ic", ic), own ? C(name) : h("span", name));
      let target = null;
      anDrag(el, { onTap: () => insertTile(ref), ghost: () => { const g = el.cloneNode(true); g.classList.add("an-ghost"); return g; },
        onMove: (x, y) => { target = anGridTarget(grid, x, y); }, onDrop: () => { anGridMark(grid, null); if (target) insertTile(ref, target.index); target = null; }, onCancel: () => anGridMark(grid, null) });
      return el;
    };
    pal.replaceChildren(h("div.row.an-dpal-h", h("span.small.muted.grow", T("Drag a report onto the dashboard – or tap it to add it at the end.")),
      h("button.btn.small", { type: "button", onclick: () => anAddPicker(refOf, insertTile) }, "＋ ", T("Add report"))),
      h("div.an-pal", ...AN.meta.templates.map(t => chipOf("t:" + t.key, t.icon, t.title)), ...AN.meta.reports.map(r => chipOf("r:" + r.id, "⭐", r.name, true))));
  };
  const drawGrid = () => {
    const [a, b] = anPeriod(cur.period || { type: "month" });
    grid.classList.toggle("editing", AN.edit);
    if (!cur.tiles.length) { grid.replaceChildren(anEmpty("🧩", AN.edit ? T("Drag reports here – or tap «+ Add report».") : T("This dashboard is empty – tap «Edit» to add reports."))); return; }
    grid.replaceChildren(...cur.tiles.map((t, i) => {
      const ref = refOf(t.ref);
      const tile = h("div.an-tile", { "data-w": t.w, "data-h": t.h, "data-i": i, style: { "--w": t.w } });
      const body = h("div.an-tbody");
      const title = t.title || (ref ? ref.title : anTr(T("Report not found")));
      const head = h("div.an-thead", AN.edit ? h("span.an-handle", { title: T("Move"), "aria-hidden": "true" }, "⠿") : null,
        h("span.an-ttitle", { translate: t.title || (ref && ref.own) ? "no" : null }, ref ? ref.icon + " " : "⚠️ ", title),
        !AN.edit && ref ? h("button.icon-btn.an-tbtn", { type: "button", title: T("Open in Reports"), "aria-label": T("Open in Reports"), onclick: () => {
          anLoad(ref.spec, ref.own ? { kind: "r", id: t.ref.slice(2), name: ref.title } : { kind: "t", id: t.ref.slice(2), name: ref.title }); AN.showTab("rep"); } }, "↗") : null);
      tile.append(head, body);
      if (AN.edit) {
        const tb = (label, txt, fn, dis) => h("button.btn.small.ghost.an-tbtn", { type: "button", title: label, "aria-label": label, disabled: !!dis, onclick: fn }, txt);
        const move = d => { const [x] = cur.tiles.splice(i, 1); cur.tiles.splice(i + d, 0, x); drawGrid(); save({ tiles: cur.tiles }); };
        tile.append(h("div.an-tools",
          tb(anTr(T("Move back")), "◀", () => move(-1), i === 0), tb(anTr(T("Move forward")), "▶", () => move(1), i === cur.tiles.length - 1),
          tb(anTr(T("Width")), "↔ " + t.w + "/4", () => { t.w = t.w % 4 + 1; drawGrid(); save({ tiles: cur.tiles }); }),
          tb(anTr(T("Height")), "↕ " + { s: "S", m: "M", l: "L" }[t.h], () => { t.h = { s: "m", m: "l", l: "s" }[t.h]; drawGrid(); save({ tiles: cur.tiles }); }),
          tb(anTr(T("Title")), "✏️", async () => { const n = await promptDialog(T("Title of the tile (empty: the name of the report)"), t.title || "", { maxLength: 60 }); if (n == null) return; t.title = n.trim(); drawGrid(); save({ tiles: cur.tiles }); }),
          tb(anTr(T("Remove")), "✕", () => { cur.tiles.splice(i, 1); drawGrid(); save({ tiles: cur.tiles }); })),
          h("span.an-resize", { title: T("Drag to change the size"), "aria-hidden": "true" }));
        // move: drag the tile by ⠿ (or anywhere on its head); resize: drag the corner
        let target = null;
        anDrag(tile, { handle: head, ghost: () => { const g = h("div.an-ghost.an-tile-ghost", title); return g; },
          onMove: (x, y) => { target = anGridTarget(grid, x, y, i); },
          onDrop: () => { anGridMark(grid, null); if (target && target.index !== i && target.index !== i + 1) { const [x] = cur.tiles.splice(i, 1); cur.tiles.splice(target.index > i ? target.index - 1 : target.index, 0, x); drawGrid(); save({ tiles: cur.tiles }); } target = null; },
          onCancel: () => anGridMark(grid, null) });
        const rz = tile.querySelector(".an-resize");
        let w0 = 0, h0 = 0, colW = 1;
        anDrag(tile, { handle: rz, threshold: 2,
          onStart: () => { w0 = t.w; h0 = AN_HEIGHTS[t.h]; colW = (grid.clientWidth - 3 * 12) / 4 + 12; tile.classList.add("resizing"); },
          onMove: (x, y, dx, dy) => {
            const one = getComputedStyle(grid).gridTemplateColumns.split(" ").length === 1;
            const nw = one ? t.w : Math.max(1, Math.min(4, Math.round(w0 + dx / colW)));
            const want = h0 + dy, nh = want < (AN_HEIGHTS.s + AN_HEIGHTS.m) / 2 ? "s" : want < (AN_HEIGHTS.m + AN_HEIGHTS.l) / 2 ? "m" : "l";
            tile.dataset.w = nw; tile.style.setProperty("--w", nw); tile.dataset.h = nh; const svg = body.querySelector(".an-chart"); if (svg) svg.style.height = (AN_HEIGHTS[nh] - 30) + "px";
          },
          onDrop: () => { tile.classList.remove("resizing"); const nw = +tile.dataset.w, nh = tile.dataset.h; if (nw !== t.w || nh !== t.h) { t.w = nw; t.h = nh; drawGrid(); save({ tiles: cur.tiles }); } else drawGrid(); },
          onCancel: () => { tile.classList.remove("resizing"); drawGrid(); } });
      }
      if (!ref) { body.append(anEmpty("⚠️", T("This report was removed."))); return tile; }
      const spec = { ...ref.spec, chart: t.chart || ref.spec.chart, from: anISO(a), to: anISO(b) };
      body.style.minHeight = AN_HEIGHTS[t.h] + "px";
      body.append(h("div.an-tload", h("span.spinner")));
      anTileQuery(spec).then(res => { body.style.minHeight = ""; body.replaceChildren(anRender(res, spec.chart, { height: Math.max(120, AN_HEIGHTS[t.h] - 30) })); })
        .catch(e => body.replaceChildren(anEmpty("⚠️", e && e.message ? e.message : T("This page could not be loaded"))));
      return tile;
    }));
  };
  draw();
}
const AN_TILE_CACHE = new Map();
function anTileQuery(spec) {
  const k = JSON.stringify(spec);
  if (!AN_TILE_CACHE.has(k)) { const p = api("parent/analytics/query", { method: "POST", body: spec }); AN_TILE_CACHE.set(k, p); p.catch(() => AN_TILE_CACHE.delete(k)); setTimeout(() => AN_TILE_CACHE.delete(k), 60000); }
  return AN_TILE_CACHE.get(k);
}
function anGridTarget(grid, x, y, self = -1) {
  const tile = document.elementFromPoint(x, y)?.closest(".an-tile");
  if (!grid.contains(document.elementFromPoint(x, y))) { anGridMark(grid, null); return null; }
  let index = grid.querySelectorAll(".an-tile").length;
  if (tile) { const r = tile.getBoundingClientRect(), i = +tile.dataset.i; index = x < r.left + r.width / 2 ? i : i + 1; anGridMark(grid, tile, x < r.left + r.width / 2 ? "before" : "after"); }
  else anGridMark(grid, null, "end");
  return { index };
}
function anGridMark(grid, tile, side) {
  grid.querySelectorAll(".an-tile.drop-before, .an-tile.drop-after").forEach(t => t.classList.remove("drop-before", "drop-after"));
  grid.classList.toggle("drop-end", side === "end");
  if (tile) tile.classList.add("drop-" + side);
}

/** A small menu under a button: [[label, icon, fn], …] – Esc and a tap outside close it. */
function anMenu(btn, items) {
  document.querySelectorAll(".an-menu").forEach(m => m.remove());
  const r = btn.getBoundingClientRect();
  const close = () => { menu.remove(); document.removeEventListener("pointerdown", out, true); document.removeEventListener("keydown", esc, true); };
  const out = e => { if (!menu.contains(e.target)) close(); };
  const esc = e => { if (e.key === "Escape") { e.stopPropagation(); close(); btn.focus(); } };
  const menu = h("div.an-menu", { role: "menu" }, ...items.map(([label, ic, fn]) => h("button", { type: "button", role: "menuitem", onclick: () => { close(); fn(); } }, h("span.an-mic", ic || ""), h("span", anTr(label)))));
  document.body.append(menu);
  const w = menu.offsetWidth;
  menu.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.right - w)) + "px";
  menu.style.top = (r.bottom + 4 + scrollY) + "px";
  setTimeout(() => { document.addEventListener("pointerdown", out, true); document.addEventListener("keydown", esc, true); });
  menu.querySelector("button")?.focus();
  return menu;
}

/** «+ Add report»: templates and «My reports» in a list – tap one. */
function anAddPicker(refOf, insertTile) {
  const m = modal(h("div.an-addpick", h("h2", T("Add report")),
    h("div.small.muted", T("Templates")), h("div.an-tpls", ...AN.meta.templates.map(t => h("button.an-tpl", { type: "button", onclick: () => { m.close(); insertTile("t:" + t.key); } }, h("span.an-tpl-ic", t.icon), h("span", t.title)))),
    h("div.small.muted", T("My reports")),
    AN.meta.reports.length ? h("div.an-tpls", ...AN.meta.reports.map(r => h("button.an-tpl", { type: "button", onclick: () => { m.close(); insertTile("r:" + r.id); } }, h("span.an-tpl-ic", "⭐"), C(r.name))))
      : h("p.small.muted", T("No saved reports yet – build one below and save it.")),
    h("div.row", h("button.btn.ghost", { type: "button", onclick: () => m.close() }, T("Close")))), { wide: true });
}

// ---------------------------------------------------------------- the period picker (quick ranges + a month calendar)
function anPicker(anchor, p, onPick) {
  document.querySelectorAll(".an-pick-back").forEach(x => x.remove());
  const today = new Date(); today.setHours(12, 0, 0, 0);
  let [a, b] = anPeriod(p), type = p.type, picking = false;
  let view = new Date(b.getFullYear(), b.getMonth(), 1, 12), mode = "days", focusDay = new Date(b);
  const quick = [["today", T("Today")], ["yesterday", T("Yesterday")], ["week", T("This week")], ["month", T("This month")], ["quarter", T("This quarter")],
    ["year", T("This year")], ["l7", T("Last 7 days")], ["l30", T("Last 30 days")], ["l365", T("Last 365 days")], ["r12", T("Last 12 months")]];
  const applyQuick = k => {
    if (k === "today") { [a, b] = [today, today]; type = "day"; }
    else if (k === "yesterday") { const y = anAddDays(today, -1); [a, b] = [y, y]; type = "day"; }
    else if (["week", "month", "quarter", "year", "r12"].includes(k)) { [a, b] = anPeriodAt(k, today); type = k; }
    else { const n = { l7: 7, l30: 30, l365: 365 }[k]; [a, b] = [anAddDays(today, -(n - 1)), today]; type = "custom"; }
    picking = false; view = new Date(b.getFullYear(), b.getMonth(), 1, 12); focusDay = new Date(b); draw();
  };
  const back = h("div.an-pick-back", { onclick: e => { if (e.target === back) close(); } });
  const sheet = h("div.an-pick", { role: "dialog", "aria-modal": "true", "aria-label": T("Choose a period") });
  back.append(sheet);
  const prevFocus = document.activeElement;
  const close = () => { back.remove(); document.removeEventListener("keydown", key, true); if (prevFocus && prevFocus.isConnected) prevFocus.focus(); };
  const select = () => {
    const same = type !== "custom" && type !== "day" && anISO(anPeriodAt(type, a)[0]) === anISO(a) && anISO(anPeriodAt(type, a)[1]) === anISO(b);
    const isToday = type === "day" && anISO(a) === anISO(today) && anISO(b) === anISO(today);
    onPick(isToday || (same && anISO(anPeriodAt(type, today)[0]) === anISO(a)) ? { type } : { type: type === "day" && anISO(a) !== anISO(b) ? "custom" : type, from: anISO(a), to: anISO(b) });
    close();
  };
  const loc = I18N.locale, fd = anFirstDay();
  const draw = () => {
    const ql = h("div.an-pick-quick", { role: "group", "aria-label": T("Quick ranges") }, ...quick.map(([k, n]) => h("button", { type: "button", onclick: () => applyQuick(k) }, n)));
    const title = mode === "days" ? view.toLocaleDateString(loc, { month: "long", year: "numeric" }) : String(view.getFullYear());
    const nav = d => { view = mode === "days" ? anAddMonths(view, d) : new Date(view.getFullYear() + d, view.getMonth(), 1, 12); draw(); };
    const head = h("div.an-cal-head",
      h("button.icon-btn", { type: "button", "aria-label": T("Back"), title: T("Back"), onclick: () => nav(-1) }, "‹"),
      h("strong.grow.center", { translate: "no", "aria-live": "polite" }, title),
      h("button.icon-btn", { type: "button", "aria-label": mode === "days" ? T("Choose month and year") : T("Back to the days"), title: mode === "days" ? T("Choose month and year") : T("Back to the days"),
        onclick: () => { mode = mode === "days" ? "months" : "days"; draw(); } }, anIcon("M4 6h16v14H4zM4 10h16M8 3v5M16 3v5")),
      h("button.icon-btn", { type: "button", "aria-label": T("Next"), title: T("Next"), onclick: () => nav(1) }, "›"));
    let body;
    if (mode === "months") {
      body = h("div.an-cal-months", ...Array.from({ length: 12 }, (_, i) => {
        const d = new Date(view.getFullYear(), i, 1, 12), on = d.getFullYear() === b.getFullYear() && i === b.getMonth();
        return h("button" + (on ? ".on" : ""), { type: "button", onclick: () => { view = d; mode = "days"; draw(); } }, d.toLocaleDateString(loc, { month: "short" }));
      }));
    } else {
      const start = anAddDays(view, -((view.getDay() - fd + 7) % 7));
      const wd = Array.from({ length: 7 }, (_, i) => h("span.an-wd", { "aria-hidden": "true" }, anAddDays(start, i).toLocaleDateString(loc, { weekday: "narrow" })));
      const lo = picking ? a : a, hi = picking ? a : b;
      const days = Array.from({ length: 42 }, (_, i) => {
        const d = anAddDays(start, i), iso = anISO(d), inR = iso >= anISO(lo) && iso <= anISO(hi);
        const cls = [d.getMonth() !== view.getMonth() ? "out" : "", inR ? "in" : "", iso === anISO(lo) ? "s" : "", iso === anISO(hi) ? "e" : "", iso === anISO(today) ? "today" : ""].filter(Boolean).join(".");
        const btn = h("button.an-day" + (cls ? "." + cls : ""), { type: "button", "data-d": iso, tabindex: iso === anISO(focusDay) ? 0 : -1,
          "aria-label": d.toLocaleDateString(loc, { weekday: "long", day: "numeric", month: "long", year: "numeric" }), "aria-pressed": String(inR),
          onclick: () => { focusDay = d; if (!picking) { a = d; b = d; picking = true; } else { if (d < a) { b = a; a = d; } else b = d; picking = false; } type = "custom"; if (d.getMonth() !== view.getMonth()) view = new Date(d.getFullYear(), d.getMonth(), 1, 12); draw(); sheet.querySelector(`.an-day[data-d="${anISO(d)}"]`)?.focus(); } },
          h("span", String(d.getDate())));
        return btn;
      });
      body = h("div.an-cal-grid", { role: "grid", onkeydown: e => {
        const step = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }[e.key];
        if (!step) return;
        e.preventDefault();
        focusDay = anAddDays(focusDay, step);
        if (focusDay.getMonth() !== view.getMonth() || focusDay.getFullYear() !== view.getFullYear()) view = new Date(focusDay.getFullYear(), focusDay.getMonth(), 1, 12);
        draw(); sheet.querySelector(`.an-day[data-d="${anISO(focusDay)}"]`)?.focus();
      } }, ...wd, ...days);
    }
    const fmtD = d => d.toLocaleDateString(loc, { day: "numeric", month: "short", year: "numeric" });
    sheet.replaceChildren(h("div.an-pick-main", ql, h("div.an-cal", head, body)),
      h("div.an-pick-foot", h("span.small.muted.grow", { translate: "no" }, picking ? fmtD(a) + " – …" : anISO(a) === anISO(b) ? fmtD(a) : fmtD(a) + " – " + fmtD(b)),
        h("button.btn.small.ghost", { type: "button", onclick: close }, T("Cancel")), h("button.btn.small", { type: "button", disabled: picking, onclick: select }, T("Select"))));
  };
  const key = e => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); } };
  document.addEventListener("keydown", key, true);
  draw();
  document.body.append(back);
  // wide screens: a popover under the timeline; phones: a sheet from the bottom (CSS)
  const r = anchor.getBoundingClientRect();
  if (innerWidth > 640) { sheet.style.left = Math.max(8, Math.min(innerWidth - sheet.offsetWidth - 8, r.left)) + "px"; sheet.style.top = Math.min(innerHeight - sheet.offsetHeight - 8, r.bottom + 6) + "px"; }
  (sheet.querySelector('.an-day[tabindex="0"]') || sheet.querySelector("button")).focus({ preventScroll: true });
}
