// ---------------------------------------------------------------- 🧹 Chores: chore plan and the Family Planer's chores
// A part of the parent area (parent.js): loaded after it, before boot() runs (eltern.html).
"use strict";

// ---------------------------------------------------------------- chore plan (Ämtliplan)
const WEEKDAYS = [T("Mon"), T("Tue"), T("Wed"), T("Thu"), T("Fri"), T("Sat"), T("Sun")];
const FREQ = { daily: T("every day"), weekdays: T("on certain weekdays"), weekly: T("once a week"), once: T("once") };

function choreConfirmList(list, after) {
  return h("ul.list", ...list.map(t => h("li.row",
    h("span.big-ic", t.icon), h("span.grow", C(t.profile_name, "strong"), " – ", C(t.name), h("span.small.muted", " · +" + fmt(t.points))),
    h("button.btn.small.good", { onclick: () => decideChore(t.id, true) }, "✓ ", T("OK")),
    h("button.btn.small.ghost", { onclick: () => decideChore(t.id, false) }, "↻ ", T("Once more")))));
  async function decideChore(id, ok) {
    await call(`parent/chores/tasks/${id}`, { method: "POST", body: { ok } });
    toast(ok ? T("Confirmed – points booked") : T("Back to open"), "good");
    after();
  }
}

async function choresView(main) {
  const [d, profiles] = await Promise.all([call("parent/chores"), call("parent/profiles")]);
  P.accounts = await call("parent/accounts");
  const kids = profiles.filter(p => p.role === "kid");
  const kidName = id => (kids.find(k => k.id === id) || {}).name || "?";
  const today = new Date().toISOString().slice(0, 10);
  const plan = h("div.scroll", h("table.tbl.weekplan",
    h("thead", h("tr", ...d.week.days.map((day, i) => h("th" + (day.day === today ? ".today" : ""), WEEKDAYS[i], h("br"),
      h("span.small", new Date(day.day + "T12:00").toLocaleDateString(I18N.locale, { day: "numeric", month: "numeric" })))))),
    h("tbody", h("tr", ...d.week.days.map(day => h("td" + (day.day === today ? ".today" : ""), ...day.entries.map(e =>
      h("div.plan-entry" + (e.weekly ? ".weekly" : ""), h("span", e.icon + " "), C(e.name, "strong"),
        h("div.small", ...e.profiles.map(pid => C(kidName(pid), "span.plan-kid")))))))))));
  const status = { open: "○", pending: "⏳", done: "✓" };
  // Two chore systems: Family Quest's own chore list (this page, d.chores) and the built-in Family Planer (the frame).
  // They do not share data – «Move my chores to the Planner» copies the own list over and switches it off. So the page
  // shows the one in use first: the own list while it has active chores (the Planner below, folded, with the move
  // button), otherwise the Planner (the switched-off own chores folded below as «Old chore list»).
  const own = d.chores.filter(c => c.active);
  const useOwn = own.length > 0;
  const moveBtn = own.some(c => c.frequency !== "once") ? h("button.btn.ghost", { onclick: async () => {
      if (!(await confirmDialog(I18N.tr(T("Move the chores of this list into the Planner? They are switched off here (their history stays)."))))) return;
      const r = await call("planer/chores/take-over", { method: "POST" });
      toast(I18N.tr(T("{0} chores moved to the Planner")).replace("{0}", r.moved.length), "good");
      if (r.kept.length) toast(I18N.tr(T("One-off chores stay here – create them as special chores in the Planner: {0}")).replace("{0}", r.kept.join(", ")));
      render();
    } }, "➡️ ", T("Move my chores to the Planner")) : null;
  const addBtn = h("button.btn", { onclick: () => choreDialog(null, kids) }, "+ ", T("Add chore"));
  const allTitle = "🧹 " + I18N.tr(useOwn ? T("All chores") : T("Old chore list"));
  const allBox = section(allTitle, h("ul.list", ...d.chores.map(c => h("li.row" + (c.active ? "" : ".off"),
      h("span.big-ic", c.icon), h("div.grow", C(c.name, "strong"),
        h("div.small.muted", FREQ[c.frequency] || c.frequency,
          c.frequency === "weekdays" ? " (" + c.weekdays.map(i => I18N.tr(WEEKDAYS[i])).join(", ") + ")" : "",
          c.frequency === "once" ? " " + fmtDate(c.date) : "", " · ",
          c.assign === "rotate" ? I18N.tr(T("rotating")) : I18N.tr(T("fixed")), ": ", C(c.profiles.map(kidName).join(", ")), " · ",
          c.kind === "duty" ? I18N.tr(T("duty")) : I18N.tr(T("bonus")), " · +" + fmt(c.points), c.energy ? " · 🔋+" + c.energy : "",
          c.confirm ? " · 👪 " + I18N.tr(T("parents confirm")) : "", c.active ? "" : " · " + I18N.tr(T("switched off")))),
      h("button.btn.small.ghost", { onclick: () => choreDialog(c, kids) }, "✏️ ", T("Edit"))))));
  allBox.dataset.fold = "all";
  const nChores = n => n === 1 ? I18N.tr(T("1 chore")) : I18N.tr(T("{0} chores")).replace("{0}", n);
  allBox.dataset.status = nChores(d.chores.length) +
    (d.chores.length > own.length ? " · " + I18N.tr(T("switched off: {0}")).replace("{0}", d.chores.length - own.length) : "");
  const planerBox = planerChoresSection();
  const planerStatus = h("span.small.muted.planer-count", { "aria-live": "polite" });
  planerBox.querySelector(".planer-frame").addEventListener("fq-planer-chores", e => {
    const n = e.detail || 0;
    planerStatus.textContent = n ? I18N.tr(T("Chores in the Planner: {0}")).replace("{0}", n)
      : useOwn ? I18N.tr(T("No chores in the Planner yet – your chores are in the list above")) : "";
    if (planerFold) planerFold.querySelector(".set-status").textContent = planerStatus.textContent;
  });
  let planerFold = null;
  if (useOwn) {
    const week = section("📅 " + I18N.tr(T("This week")), plan);
    week.dataset.fold = "week";
    week.dataset.status = nChores(own.length);
    const todayBox = d.today.length ? section("✅ " + I18N.tr(T("Today")), h("ul.list", ...d.today.map(t => h("li.row", h("span.status-ic." + t.status, status[t.status] || ""),
      h("span", t.icon), C(t.name, "span.grow"), C(t.profile_name, "span.muted"))))) : null;
    if (todayBox) {
      todayBox.dataset.fold = "today";
      todayBox.dataset.status = I18N.tr(T("Done: {0} of {1}")).replace("{0}", d.today.filter(t => t.status === "done").length).replace("{1}", d.today.length);
    }
    if (!P.choresFolds) { P.choresFolds = true; SET_OPEN.add("chores.week"); SET_OPEN.add("chores.today"); }    // open at first
    const ownList = h("div.chores-own", week, todayBox, allBox);
    foldBoxes(ownList, "chores");
    planerFold = setFold("chores.planer", "📅 " + I18N.tr(T("Chore plan")), planerBox);
    planerFold.querySelector(".set-status").textContent = I18N.tr(T("Separate chore plan – empty until you move your chores there"));
    planerBox.querySelector(".sec-head h2").classList.add("fold-title");
    main.append(pageHead(T("Chores"), addBtn),
      d.pending.length ? section("⏳ " + I18N.tr(T("Chores to confirm")), choreConfirmList(d.pending, render)) : null,
      setGroup("chores.own", "🧹", T("Family Quest chores")), ...ownList.children,
      setGroup("chores.planer", "📅", T("Planner"), moveBtn), planerFold,
      planerSettingsSection());
  } else {
    planerBox.append(planerStatus);
    const old = h("div.chores-own", d.chores.length ? allBox : null);
    if (d.chores.length) { allBox.dataset.fold = "old"; foldBoxes(old, "chores"); }
    main.append(pageHead(T("Chores")),
      d.pending.length ? section("⏳ " + I18N.tr(T("Chores to confirm")), choreConfirmList(d.pending, render)) : null,
      planerBox, ...old.children,
      planerSettingsSection());
  }
}

// 📅 The Family Planer's chore plan in the parent area (planer?mode=parent in a frame). The planer's own top bar
// (clock, season, its buttons) is hidden there (planer.html) – its functions are buttons in this section head:
// 🏖️ holidays (only when the planer checks holidays; the number = holidays waiting for a decision), «+ Special chore»,
// «+ To-do». They call the planer in the frame (planer/host.js FQ_PLANER_DO) – same windows, PIN rules and API calls.
// «Refresh» (the planer pulls calendars and lists again) is the app's ⟳ button (planerRefresh). Settings: below.
function planerChoresSection(...more) {
  const frame = planerFrame("planner?mode=parent#/aemtliplan", T("Chore plan"));
  const act = kind => {
    const w = frame.contentWindow;
    if (!w || !w.FQ_PLANER_DO) return;
    w.FQ_PLANER_DO(kind);
  };
  const dot = h("span.chip.warn.planer-dot", { hidden: true });
  const vac = h("button.btn.small.ghost", { hidden: true, title: T("Holidays and absences in the calendar: who is away, are chores paused?"),
    onclick: () => act("vac") }, "🏖️ ", T("Holidays"), dot);
  frame.addEventListener("fq-planer-state", e => {
    const st = e.detail || {};
    vac.hidden = !st.vac; vac.classList.toggle("on", !!st.open);
    dot.hidden = !st.pending; dot.textContent = st.pending ? String(st.pending) : "";
  });
  return sectionAdd("📅 " + I18N.tr(T("One chore plan: the Planner")), [vac,
      h("button.btn.small.ghost", { onclick: () => act("special") }, "+ ", T("Special chore")),
      h("button.btn.small.ghost", { onclick: () => act("todo") }, "+ ", T("To-do"))],
    frame, ...more);
}

// ⚙️ the planer's settings (persons, points, holidays, lists …, with the planer's own parent PIN) – folded at the
// bottom like the settings of the other sections; the frame loads only when opened
function planerSettingsSection() {
  const box = h("details.card.sec.fold.planer-settings", h("summary", h("h2", "⚙️ " + I18N.tr(T("Planner settings")))));
  box.addEventListener("toggle", () => {
    if (box.open && !box.querySelector(".planer-frame")) box.append(planerFrame("planner?mode=parent#/einstellungen", T("Planner settings")));
  });
  return box;
}

// the app's ⟳ button: on the Chores page the planer first pulls its calendars and lists again (at most 8 s)
function planerRefresh() {
  const w = [...document.querySelectorAll(".planer-frame")].map(f => f.contentWindow).find(x => x && x.FQ_PLANER_DO);
  return w ? Promise.race([w.FQ_PLANER_DO("refresh"), new Promise(r => setTimeout(r, 8000))]).catch(() => {}) : Promise.resolve();
}

function choreDialog(c, kids) {
  const isNew = !c;
  c = c || { name: "", icon: "🧹", points: 10, account: "coins", frequency: "daily", weekdays: [], date: "", assign: "fixed",
    rotate_every: "week", profiles: kids.map(k => k.id), kind: "bonus", confirm: true, active: true };
  const f = {
    icon: h("input.icon-in", { type: "text", value: c.icon }), name: h("input", { type: "text", value: c.name, placeholder: T("e.g. set the table") }),
    points: h("input", { type: "number", min: 0, value: c.points }),
    account: h("select", ...P.accounts.filter(a => a.active).map(a => h("option", { value: a.key, selected: a.key === c.account }, a.icon + " " + I18N.tr(a.name)))),
    frequency: h("select", ...Object.entries(FREQ).map(([k, n]) => h("option", { value: k, selected: k === c.frequency }, n))),
    date: h("input", { type: "date", value: c.date || "" }),
    assign: h("select", h("option", { value: "fixed", selected: c.assign === "fixed" }, T("Fixed: every chosen child")),
      h("option", { value: "rotate", selected: c.assign === "rotate" }, T("Rotating: one child after the other"))),
    rotate_every: h("select", h("option", { value: "week", selected: c.rotate_every === "week" }, T("changes every week")),
      h("option", { value: "day", selected: c.rotate_every === "day" }, T("changes every day"))),
    kind: h("select", h("option", { value: "bonus", selected: c.kind === "bonus" }, T("Bonus chore (full points)")),
      h("option", { value: "duty", selected: c.kind === "duty" }, T("Duty (few or no points)"))),
    confirm: h("input", { type: "checkbox", checked: !!c.confirm }), active: h("input", { type: "checkbox", checked: !!c.active }),
    energy: h("input", { type: "number", min: 0, max: 20, step: 1, inputmode: "numeric", value: c.energy || 0 }),
  };
  const days = WEEKDAYS.map((n, i) => h("label.check", h("input", { type: "checkbox", value: i, checked: c.weekdays.includes(i) }), n));
  const who = kids.map(k => h("label.check", h("input", { type: "checkbox", value: k.id, checked: c.profiles.includes(k.id) }), C(k.name)));
  const dayRow = h("div.row", ...days), dateRow = h("label.field", T("Date"), f.date), rotRow = h("label.field", T("Rotation"), f.rotate_every);
  const sync = () => { dayRow.hidden = f.frequency.value !== "weekdays"; dateRow.hidden = f.frequency.value !== "once"; rotRow.hidden = f.assign.value !== "rotate"; };
  f.frequency.addEventListener("change", sync); f.assign.addEventListener("change", sync); sync();
  const m = modal(h("div.form",
    h("h2", isNew ? T("New chore") : T("Edit chore")),
    h("div.row", f.icon, h("label.field.grow", T("Name"), f.name)),
    h("div.field-row", h("label.field", T("Points"), f.points), h("label.field", T("Account"), f.account), h("label.field", T("Type"), f.kind),
      h("label.field", h("span", "⚡ ", T("Energy bonus"), fieldInfo(T("Segments of the game battery the child gets when the chore is done (0 = none). Never more than the battery holds."))), f.energy)),
    h("div.grid3", h("label.field", T("How often"), f.frequency), dateRow, h("label.field", T("Assignment"), f.assign), rotRow), dayRow,
    h("div", h("strong", T("Who")), h("div.row", ...who)),
    h("label.check", f.confirm, T("Parents confirm before points are booked")), h("label.check", f.active, T("Active")),
    h("div.row", h("button.btn", { onclick: save }, T("Save")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")), h("span.grow"),
      !isNew ? h("button.btn.small.bad", { onclick: remove }, T("Remove")) : null)), { wide: true });
  async function save() {
    const body = { name: f.name.value, icon: f.icon.value || "🧹", points: +f.points.value, account: f.account.value, frequency: f.frequency.value,
      weekdays: days.map(l => l.querySelector("input")).filter(x => x.checked).map(x => +x.value), date: f.date.value || null,
      assign: f.assign.value, rotate_every: f.rotate_every.value, profiles: who.map(l => l.querySelector("input")).filter(x => x.checked).map(x => +x.value),
      kind: f.kind.value, confirm: f.confirm.checked, active: f.active.checked, sort: c.sort || 0, energy: Math.max(0, Math.min(20, Math.round(+f.energy.value || 0))) };
    await call(isNew ? "parent/chores" : `parent/chores/${c.id}`, { method: isNew ? "POST" : "PUT", body });
    m.close(); toast(T("Saved"), "good"); render();
  }
  async function remove() {
    if (!(await confirmDialog(I18N.tr(T("Remove this chore? Chores already done stay in the history."))))) return;
    await call(`parent/chores/${c.id}`, { method: "DELETE" }); m.close(); render();
  }
}

// the planner in a frame (same origin): on phones as tall as its content – no second scroll area inside the page
// the frame is as high as the planer's content (no scrolling inside a scrolling page; planer.html drops its min-height
// in the parent area) – its windows open in the part visible on the screen (planer/host.js FQ_VIS)
function planerFrame(src, title) {
  const f = h("iframe.planer-frame", { src, title: I18N.tr(title) });
  const fit = () => {
    if (!f.isConnected) return clearInterval(timer);
    try {
      const root = f.contentDocument && f.contentDocument.getElementById("planer-root");
      if (root && root.offsetHeight) f.style.height = Math.max(200, Math.ceil(root.getBoundingClientRect().height) + 4) + "px";
    } catch {}
  };
  // how many chores the Planner has (the chores page says which plan is in use): «fq-planer-chores» when it changes
  let count = null;
  const tell = () => {
    try {
      const card = f.contentDocument && f.contentDocument.querySelector("family-planer-card");
      const chores = card && card._store && card._store.snap && card._store.snap.chores;
      if (Array.isArray(chores) && chores.length !== count) { count = chores.length; f.dispatchEvent(new CustomEvent("fq-planer-chores", { detail: count })); }
    } catch {}
  };
  const timer = setInterval(() => { fit(); tell(); }, 700);
  f.addEventListener("load", fit);
  return f;
}
