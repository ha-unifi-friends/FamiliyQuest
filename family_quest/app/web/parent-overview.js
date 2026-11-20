// ---------------------------------------------------------------- 📊 Overview: the children's rows, behaviour weather, profiles and the profile dialog
// A part of the parent area (parent.js): loaded after it, before boot() runs (eltern.html).
"use strict";

// ---------------------------------------------------------------- overview
async function overviewView(main) {
  const [d, accounts, profiles, persons] = await Promise.all([call("parent/overview"), call("parent/accounts"), call("parent/profiles"),
    P.meta.planer ? call("parent/ha/persons").catch(() => []) : []]);
  P.accounts = accounts; P.profiles = profiles;
  const full = id => profiles.find(x => x.id === id);
  const pend = d.pending.length ? h("section.card.sec", h("ul.list", ...d.pending.map(r => h("li.row",
    h("span.big-ic", r.icon), h("span.grow", C(r.profile_name, "strong"), " – ", r.name, h("span.small.muted", " · " + fmt(r.cost))),
    h("button.btn.small.good", { onclick: () => decide(r.id, true) }, "✓ ", T("Approve")),
    h("button.btn.small.bad", { onclick: () => decide(r.id, false) }, "✗ ", T("Decline")))))) : null;
  async function decide(id, approve) { await call(`parent/redemptions/${id}`, { method: "POST", body: { approve } }); toast(approve ? T("Approved") : T("Declined"), "good"); render(); }
  const chorePend = d.chores_pending.length ? h("section.card.sec", choreConfirmList(d.chores_pending, render)) : null;
  // every child a folded row: folded it shows the weather of the day to pick and «Edit profile»; open: everything else
  const wd = await call("parent/weather").catch(() => null);
  const kids = d.kids.map(k => {
    const wk = wd && wd.config.enabled ? wd.kids.find(x => x.profile.id === k.profile.id) : null;
    const w = wk ? kidWeather(wk, wd.config) : null;
    const id = k.profile.id;
    return h("details.card.sec.kid.kid-fold", { "data-kid": id, open: KID_OPEN.has(id), ontoggle: e => e.currentTarget.open ? KID_OPEN.add(id) : KID_OPEN.delete(id) },
      h("summary",
        h("div.row.kid-head", avatarSvg(k.profile.avatar, 48), h("div.grow", C(k.profile.name, "h2"),
          // folded: level, streak and what the child can spend (coins …) – the rest when opened
          h("span.muted", I18N.tr(T("Level {0}")).replace("{0}", k.level.level) + " · 🔥 " + k.streak +
            P.accounts.filter(a => a.active && a.spendable && a.key !== "internet").map(a => " · " + (a.icon || "") + " " + fmt(k.balances[a.key] || 0, 1)).join("")), " ", loginChip(k.profile),
          k.sad_since ? h("span.mood-flag", { title: I18N.tr(T("feels sad")) }, " 😢") : null)),
        // a tap on these buttons does not open the row
        h("div.row.wrap.kid-quick", { onclick: e => { if (e.target.closest("button")) e.preventDefault(); } },
          h("button.btn.small.ghost", { onclick: () => profileDialog(full(id) || k.profile, persons) }, "✏️ ", T("Edit profile")),
          w ? w.pick : null)),
      k.sad_since ? h("div.mood-note", "😢 ", T("feels sad"), " (", T("since"), " ",
        new Date(k.sad_since).toLocaleString(I18N.locale, { weekday: "short", hour: "2-digit", minute: "2-digit" }), ")") : null,
      k.mood_text || k.mood ? h("div.mood-text", h("span.mood-emoji", k.mood || "💬"), " ", T("Today I feel …"), " ", k.mood_text ? C("«" + k.mood_text + "»", "strong") : null,
        k.mood_text_at ? h("span.small.muted", " · " + new Date(k.mood_text_at).toLocaleString(I18N.locale, { weekday: "short", hour: "2-digit", minute: "2-digit" })) : null) : null,
      h("div.row.kid-actions",
        h("button.btn.small" + (k.profile.crown ? "" : ".ghost"), { title: T("Crown for today"), onclick: async () => {
          await call(`parent/profiles/${id}/crown`, { method: "POST", body: { on: !k.profile.crown } });
          toast(k.profile.crown ? T("Crown taken off") : T("👑 Crown for today!"), "good"); render();
        } }, "👑"),
        h("button.btn.small.ghost", { onclick: () => bookDialog(k.profile) }, "± ", T("Book points"))),
    h("div.kpis",
      kpi(T("XP this week"), fmt(k.week.xp)), kpi(T("Daily goal this week"), k.week.goal_percent + " %"),
      kpi(T("Days with goal"), String(k.week.days_met)), kpi(T("Minutes this week"), fmt(k.week.minutes)),
      ...P.accounts.filter(a => a.active && a.spendable && !(a.key === "internet" && k.internet)).map(a => kpi(a.icon + " " + I18N.tr(a.name), fmt(k.balances[a.key], 1))),
      k.chores && k.chores.reliability != null ? kpi("🧹 " + I18N.tr(T("Chores reliability")), fmt(k.chores.reliability) + " %") : null,
      k.internet ? h("div.kpi" + (k.internet.running ? ".net-on" : ""), h("b", (k.internet.running ? "🟢 " : "🌐 ") + fmt(k.internet.minutes) + " min"),
        h("span.small.muted", k.internet.running ? I18N.tr(T("Internet is on")) : I18N.tr(T("Internet time"))),
        k.internet.running ? h("button.btn.small.bad", { onclick: async () => { await call(`parent/internet/${k.profile.id}/stop`, { method: "POST" }); toast(T("Internet stopped"), "good"); render(); } }, "⏸ ", T("Stop")) : null) : null),
    k.pets && k.pets.length ? petsBox(k, render) : null,
    h("div.cols",
      h("div", h("h3", T("Packs")), k.packs.length ? h("ul.list", ...k.packs.map(p => h("li", h("div.row", C(p.title, "span.grow"), h("b", p.percent + " %"),
        p.due ? chip(p.due + " " + I18N.tr(T("due")), "warn") : null), bar(p.percent, 100, p.color)))) : h("p.muted", T("No packs active."))),
      h("div", h("h3", T("Learning time per subject (7 days)")), k.subjects.length ? h("table.tbl", h("tbody", ...k.subjects.map(s =>
        h("tr", h("td", subjectName(s.subject)), h("td.num", s.answers + " " + I18N.tr(T("answers"))), h("td.num", Math.round(100 * s.right / Math.max(1, s.answers)) + " %"),
          h("td.num", fmt(s.minutes, 1) + " min"))))) : h("p.muted", T("Nothing learnt yet this week."))),
      h("div", h("h3", T("Weak spots")), k.weak.length ? h("ul.list.weak", ...k.weak.map(w => h("li", C(w.label, "strong"),
        h("div.small.muted", C(w.unit), " · ", w.wrong + " / " + w.tries + " " + I18N.tr(T("wrong")))))) : h("p.muted", T("No weak spots yet – great!")))),
    w ? h("div.kid-weather", h("h3", "⛅ ", T("Weather of the day")), w.hist) : null);
  });
  const failed = await call("parent/logins/failed?days=30").catch(() => []);
  // folded, the number in the title – details only when wanted
  const failBox = failed.length ? h("details.card.sec.fold", h("summary", h("h2", "🔐 " + I18N.tr(T("Failed logins (30 days)")) + " ", chip(String(failed.length), "warn"))),
    h("div.scroll", h("table.tbl.logins",
      h("thead", h("tr", h("th", T("When")), h("th", T("Profile")), h("th", T("IP address")), h("th", "MAC"), h("th", T("Device")), h("th", T("Usually")))),
      h("tbody", ...failed.map(r => h("tr",
        h("td", new Date(r.at.replace(" ", "T")).toLocaleString(I18N.locale, { day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" })),
        h("td", r.kind === "parent" ? I18N.tr(T("Parent area")) : r.kind === "blocked" ? "🛡️ " + I18N.tr(T("Blocked network")) : C(r.profile_name || "?")),
        h("td.mono", r.ip || "–"), h("td.mono", r.mac || "–"), h("td", r.device ? C(r.device) : "–"),
        h("td", r.usual ? h("span", C(r.usual.name), h("span.small.muted", " (" + r.usual.n + "×)")) : h("span.warn-text", T("nobody yet")))))))))
    : null;
  main.append(pageHead(T("Overview"),
      P.meta.planer ? h("button.btn.ghost", { onclick: importPersons }, "📅 ", T("Take over from Family Planer")) : null,
      h("button.btn.ghost", { onclick: () => profileDialog(null, persons, "parent") }, "+ ", T("Add parent")),
      h("button.btn", { onclick: () => profileDialog(null, persons, "kid") }, "+ ", T("Add child"))), d.kids.length ? partyCard() : null,
    // groups on the page background like «Family» and «Settings»: their heading with the ⓘ, the rows below
    ...(pend ? [setGroup("Waiting for your approval", "⏳", T("Waiting for your approval")), pend] : []),
    ...(chorePend ? [setGroup("Chores to confirm", "🧹", T("Chores to confirm")), chorePend] : []),
    pend || chorePend ? null : h("p.muted.ov-none", "✓ ", T("No open approvals.")),
    ...(d.family_goal ? [setGroup("Family goal", "🤝", T("Family goal")), h("section.card.sec.ov-goal", h("div.row", C(d.family_goal.title, "strong.grow"), h("b", fmt(d.family_goal.value) + " / " + fmt(d.family_goal.target))),
      bar(d.family_goal.value, d.family_goal.target, "var(--good)"))] : []),
    setGroup("ov.kids", "🧒", T("Children")),
    ...(kids.length ? kids : [h("div.card", h("p", T("No child profile yet.")))]),
    setGroup("Parents", "👪", T("Parents")),
    profileCards(profiles.filter(p => p.role === "parent"), persons),
    ...(await archivedSection()),
    failBox ? setGroup("ov.security", "🔐", T("Security")) : null, failBox);                                    // the failed logins: at the very bottom
  async function importPersons() {
    const r = await call("parent/ha/import_persons", { method: "POST" });
    toast(r.created.length ? I18N.tr(T("Created: {0}")).replace("{0}", r.created.join(", ")) : T("All persons are already linked"), "good");
    render();
  }
}

// the pets of a child (pets.py): bars and status, «holiday care» pauses them
function petsBox(k, render) {
  const paused = k.pets_paused, away = !paused && k.pets.some(p => p.paused === "away");
  return h("div.pets-box",
    h("div.row", h("h3.grow", "🐾 ", T("Pets")),
      away ? chip(I18N.tr(T("away (Family Planer)")), "") : null,
      h("button.btn.small" + (paused ? "" : ".ghost"), { title: T("While holiday care is on, the pets do not get hungry, sad or dirty."), onclick: async () => {
        await call(`parent/profiles/${k.profile.id}/pet-pause`, { method: "PUT", body: { on: !paused } });
        toast(paused ? T("Holiday care ended") : T("Holiday care is on"), "good"); render();
      } }, paused ? "▶ " : "⏸ ", paused ? T("End holiday care") : T("Holiday care"))),
    h("div.pet-mini-list", ...k.pets.map(p => h("div.pet-mini" + (p.dying ? ".dying" : ""),
      h("span.pet-mini-ic", petIcon(p.kind, 34, p.emoji)), h("div.grow", h("div", C(p.name, "strong"), h("span.small.muted", " · " + I18N.tr(p.age === 1 ? T("1 day old") : T("{0} days old")).replace("{0}", p.age))),
        h("div.pet-mini-bars", ...[["hunger", "🍖"], ["mood", "😊"], ["clean", "🫧"]].map(([b, ic]) => h("span.pet-mini-bar", { title: ic + " " + p[b] }, ic,
          bar(p[b], 100, p[b] < 25 ? "var(--bad)" : p[b] < 50 ? "var(--warn)" : "var(--good)")))),
        p.dying ? h("div.small.warn-text", "🆘 ", I18N.tr(T("All bars empty – dies in {0} days")).replace("{0}", Math.max(0, Math.ceil(p.days_left)))) : null)))));
}

// archived (inactive) profiles: restore or delete for good
async function archivedSection() {
  let list = []; try { list = await call("parent/profiles/archived"); } catch {}
  if (!list.length) return [];
  return [setGroup("Archived profiles", "🗄️", T("Archived profiles")), h("section.card.sec.ov-archived",
    h("ul.list", ...list.map(p => h("li.row", avatarSvg(p.avatar, 36), C(p.name, "strong.grow"),
      h("button.btn.small.ghost", { onclick: async () => { await call(`parent/profiles/${p.id}/restore`, { method: "POST" }); toast(T("Restored"), "good"); render(); } }, "↩️ ", T("Restore")),
      h("button.btn.small.bad", { onclick: () => removeDialog(p, true) }, "🗑 ", T("Delete"))))))];
}

// removing a profile: type the name again, choose archive (inactive) or delete (gone), confirm
function removeDialog(p, archived = false, done) {
  let mode = archived ? "delete" : "archive";
  const name = h("input", { type: "text", autocomplete: "off", placeholder: p.name });
  const ok = h("input", { type: "checkbox" });
  const btn = h("button.btn.bad", { disabled: true, onclick: go });
  const modes = h("div.grid2.remove-modes");
  const okText = h("span");
  const draw = () => {
    modes.replaceChildren(...[["archive", "🗄️", T("Archive"), T("The profile becomes inactive: it disappears from the app, its history stays and you can restore it.")],
      ["delete", "🗑", T("Delete for good"), T("The profile and all its data (points, progress, history) are deleted. This cannot be undone.")]]
      .filter(([k]) => !(archived && k === "archive"))
      .map(([k, ic, n, hint]) => h("button.remove-mode" + (mode === k ? ".on" : ""), { type: "button", onclick: () => { mode = k; draw(); } },
        h("strong", ic + " ", n), h("span.small.muted", hint))));
    okText.textContent = I18N.tr(mode === "delete" ? T("Yes, delete this profile for good.") : T("Yes, archive this profile."));
    btn.textContent = I18N.tr(mode === "delete" ? T("Delete for good") : T("Archive"));
    check();
  };
  const check = () => { btn.disabled = !(ok.checked && name.value.trim().toLowerCase() === p.name.trim().toLowerCase()); };
  name.oninput = check; ok.onchange = check;
  const m = modal(h("div.form",
    h("h2", "⚠️ ", T("Remove profile")), h("div.row", avatarSvg(p.avatar, 48), C(p.name, "strong")),
    modes,
    h("label.field", I18N.tr(T("Type the name «{0}» to confirm")).replace("{0}", p.name), name),
    h("label.check", ok, okText),
    h("div.row", btn, h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  draw();
  async function go() {
    try {
      await call(`parent/profiles/${p.id}?mode=${mode}&name=${encodeURIComponent(name.value.trim())}`, { method: "DELETE" });
      m.close(); toast(mode === "delete" ? T("Profile deleted") : T("Profile archived"), "good"); done && done(); render();
    } catch (e) { toast(e.message, "bad"); }
  }
}

const kpi = (label, value) => h("div.kpi", h("b", value), h("span.small.muted", label));
const subjectName = k => { const s = (P.meta.subjects || []).find(s => s.key === k); return s ? s.icon + " " + I18N.tr(s.name) : k || "–"; };

function bookDialog(profile) {
  const acc = h("select", ...P.accounts.filter(a => a.active).map(a => h("option", { value: a.key }, a.icon + " " + I18N.tr(a.name))));
  const amount = h("input", { type: "number", value: "10", step: "1" });
  const reason = h("input", { type: "text", placeholder: T("e.g. helped with cooking") });
  const m = modal(h("div.form", h("h2", T("Book points")), C(profile.name, "strong"),
    h("label.field", T("Account"), acc), h("label.field", T("Amount (negative = deduct)"), amount), h("label.field", T("Reason"), reason),
    h("div.row", h("button.btn", { onclick: async () => {
      await call("parent/book", { method: "POST", body: { profile_id: profile.id, account: acc.value, amount: Number(amount.value), reason: reason.value } });
      m.close(); toast(T("Booked"), "good"); render();
    } }, T("Book points")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
}

// ---------------------------------------------------------------- profiles
// how a profile signs in (profile setting «login», see the profile dialog)
const LOGIN_CHIP = { none: ["🪄", T("No sign-in")], pin: ["🔢", T("PIN")], ha: ["🏠", T("Home Assistant only")], pin_ha: ["🔢🏠", T("PIN or Home Assistant")] };
function loginChip(p) {
  const c = LOGIN_CHIP[p.login];
  return c ? h("span.chip.login-chip", { title: I18N.tr(T("Sign-in")) }, c[0], " ", c[1]) : null;
}
function profileCards(list, persons) {
  if (!list.length) return h("p.muted", T("Nobody yet."));
  return h("div.profile-cards", ...list.map(p => h("div.card.pcard", avatarSvg(p.avatar, 72),
    h("div.grow", C(p.name, "h2"), h("div.small.muted", p.role === "parent" ? T("Parent") : T("Child"),
      p.planer_person_id ? " · 📅 Family Planer" : "", p.id === P.meta.me.id ? " · " + I18N.tr(T("that's you")) : ""),
      loginChip(p),
      p.role === "kid" ? h("div.small", T("Daily goal"), ": ", p.settings.daily_goal + " XP · ", T("Lesson"), ": ", p.settings.lesson_length) : null,
      p.role === "parent" && p.settings.notify_service ? h("div.small", "🔔 ", C(p.settings.notify_service)) : null),
    h("button.btn.small.ghost", { onclick: () => profileDialog(p, persons) }, "✏️ ", T("Edit")))));
}

// a select with the Home Assistant entities of some domains (the current value stays even if it is not found)
function entitySelect(current, domains) {
  const sel = h("select.grow", h("option", { value: "" }, "–"));
  const keep = v => { if (v && ![...sel.options].some(o => o.value === v)) sel.append(h("option", { value: v }, v)); sel.value = v || ""; };
  keep(current);
  if (P.meta.ha) Promise.all(domains.map(d => call("parent/ha/entities?domain=" + d).catch(() => []))).then(lists => {
    const v = sel.value;
    sel.replaceChildren(h("option", { value: "" }, "–"), ...lists.flat().map(e => h("option", { value: e.entity_id }, (e.name && e.name !== e.entity_id ? e.name + " – " : "") + e.entity_id)));
    keep(v);
  });
  else if (!current) sel.replaceChildren(h("option", { value: "" }, I18N.tr(T("Home Assistant is not connected"))));
  sel.setValue = keep;
  return sel;
}

// ---------------------------------------------------------------- time sliders (games, learning, internet per day)
// positions of the slider → minutes: minutes first, then hours; the last position (far right) is ∞ = unlimited
const LIMIT_STEPS = [0, 5, 10, 15, 20, 30, 45, 60, 75, 90, 120, 150, 180, 240, 300, 360, 480, 600, 720];
const LIMIT_STEPS_WEEK = [0, 30, 60, 90, 120, 180, 240, 300, 360, 420, 480, 600, 720, 900, 1080, 1200, 1500, 1800, 2400];

/** A master slider with a «Days» button: 7 weekday sliders (Mon … Sun) docked to it – they move with the master
 *  until one is moved on its own (undocked: own limit); moved back to the master's value it docks again.
 *  value {all: minutes|null, days: {"0".."6": minutes|null}} – null = ∞, days only the undocked ones. */
function limitSlider({ icon, label, value, steps = LIMIT_STEPS, extra = null }) {
  const v = Object.assign({ all: null, days: {} }, value || {});
  let master = v.all;                                         // minutes or null (∞)
  const own = {};                                             // undocked weekdays: own minutes or null
  for (const [k, x] of Object.entries(v.days || {})) if (/^[0-6]$/.test(k) && x !== master) own[k] = x;
  const INF = () => steps.length;                            // index of ∞
  const toMin = i => i >= INF() ? null : steps[i];
  const toIdx = m => {                                       // the nearest position (a value between steps stays as it is until moved)
    if (m == null) return INF();
    let best = 0;
    steps.forEach((x, i) => { if (Math.abs(x - m) < Math.abs(steps[best] - m)) best = i; });
    return best;
  };
  const paint = (inp, m) => { const i = toIdx(m); inp.max = INF(); inp.value = i; inp.style.setProperty("--p", (i / INF() * 100) + "%");
    inp.setAttribute("aria-valuetext", fmtMinutes(m)); };
  const masterOut = h("output.lim-val");
  const masterIn = h("input.lim-range", { type: "range", min: 0, step: 1, "aria-label": label });
  const scale = h("div.lim-scale", { "aria-hidden": "true" });
  const drawScale = () => scale.replaceChildren(...[0, Math.round(INF() * .37), Math.round(INF() * .63), INF()]
    .map(i => h("span", { style: { "--p": i / INF() } }, i === INF() ? "∞" : fmtMinutes(steps[i]))));
  const dayRows = WEEKDAYS.map((d, i) => {
    const k = String(i);
    const inp = h("input.lim-range.lim-day-range", { type: "range", min: 0, step: 1, "aria-label": I18N.tr(label) + " – " + I18N.tr(d) });
    const out = h("output.lim-val");
    const pin = h("button.lim-pin", { type: "button", onclick: () => { delete own[k]; draw(); } });
    const row = h("div.lim-day", h("span.lim-dname", d), inp, out, pin);
    inp.addEventListener("input", () => {
      const m = toMin(+inp.value);
      if (+inp.value === toIdx(master)) delete own[k]; else own[k] = m;     // back on the master's value: docked again
      draw();
    });
    return { k, row, inp, out, pin };
  });
  const week = h("div.lim-week", { hidden: true }, ...dayRows.map(r => r.row));
  const daysBtn = h("button.btn.small.ghost.lim-days", { type: "button", "aria-expanded": "false",
    onclick: () => { week.hidden = !week.hidden; draw(); } }, "📅 ", T("Days"));
  masterIn.addEventListener("input", () => { master = toMin(+masterIn.value); draw(); });
  function draw() {
    paint(masterIn, master);
    masterOut.textContent = fmtMinutes(master);
    masterIn.classList.toggle("inf", master == null);
    const n = Object.keys(own).length;
    daysBtn.setAttribute("aria-expanded", String(!week.hidden));
    daysBtn.classList.toggle("on", !week.hidden);
    daysBtn.replaceChildren(...["📅 ", I18N.tr(T("Days")), n ? h("span.lim-badge", String(n)) : ""].filter(Boolean));
    for (const r of dayRows) {
      const docked = !(r.k in own), m = docked ? master : own[r.k];
      paint(r.inp, m);
      r.out.textContent = fmtMinutes(m);
      r.row.classList.toggle("own", !docked);
      r.pin.textContent = docked ? "🔗" : "🔓";
      r.pin.title = I18N.tr(docked ? T("Moves with the slider above") : T("Own time – tap to dock again"));
      r.pin.disabled = docked;
    }
  }
  drawScale();
  if (Object.keys(own).length) week.hidden = false;         // a weekday with its own time: the days are open
  draw();
  const el = h("div.lim", h("div.lim-head", h("span.lim-ic", icon), h("b.grow", label), masterOut, extra, daysBtn),
    h("div.lim-master", masterIn, scale), week);
  return {
    el,
    value: () => ({ all: master, days: daysBtn.hidden ? {} : Object.fromEntries(Object.entries(own).filter(([, x]) => x !== master)) }),
    /** per week: no weekday sliders; other steps */
    setMode(withDays, newSteps) {
      daysBtn.hidden = !withDays;
      if (!withDays) week.hidden = true;
      if (newSteps && newSteps !== steps) { steps = newSteps; drawScale(); }
      draw();
    },
  };
}

/** Internet budget of a child: the slider (minutes per day / week, own minutes per weekday) for the time sliders,
 *  reset time and block times. A budget of 0 without weekdays and block times = no plan (only earned minutes). */
function internetPlanEditor(cur) {
  const p = Object.assign({ budget: 0, period: "day", reset: "00:00", reset_day: 0, days: {}, blocks: [] }, cur || {});
  const period = h("select.lim-period", { "aria-label": T("Internet") }, h("option", { value: "day", selected: p.period === "day" }, T("per day")), h("option", { value: "week", selected: p.period === "week" }, T("per week")));
  const slider = limitSlider({ icon: "🌐", label: T("Internet"), value: { all: p.budget, days: p.period === "day" ? p.days : {} },
    steps: p.period === "week" ? LIMIT_STEPS_WEEK : LIMIT_STEPS, extra: period });
  const reset = h("input", { type: "time", value: p.reset });
  const resetDay = h("select", ...WEEKDAYS.map((d, i) => h("option", { value: i, selected: +p.reset_day === i }, d)));
  const resetDayField = h("label.field", T("Reset on"), resetDay);
  const blocks = p.blocks.map(b => Object.assign({}, b));
  const blockBox = h("div.plan-blocks");
  const MODES = { internet: T("Family Quest works normally"), games: T("Family Quest without games"), app: T("Only a message: OfflineTime") };
  const drawBlocks = () => blockBox.replaceChildren(...blocks.map((b, bi) => h("div.plan-block",
    h("div.row.wrap", ...WEEKDAYS.map((d, i) => h("label.check", h("input", { type: "checkbox", checked: b.days.includes(i),
      onchange: e => { b.days = e.target.checked ? [...b.days, i] : b.days.filter(x => x !== i); } }), d))),
    h("div.row.wrap", h("input", { type: "time", value: b.from, onchange: e => { b.from = e.target.value; } }), "–",
      h("input", { type: "time", value: b.to, onchange: e => { b.to = e.target.value; } }),
      h("select", { onchange: e => { b.mode = e.target.value; } }, ...Object.entries(MODES).map(([k, n]) => h("option", { value: k, selected: b.mode === k }, n))),
      h("button.icon-btn", { type: "button", title: T("Delete"), onclick: () => { blocks.splice(bi, 1); drawBlocks(); } }, "🗑️")))),
    h("button.btn.small.ghost", { type: "button", onclick: () => { blocks.push({ days: [0, 1, 2, 3, 4], from: "20:00", to: "07:00", mode: "internet" }); drawBlocks(); } }, "+ ", T("Block time")));
  drawBlocks();
  const sync = () => { resetDayField.hidden = period.value !== "week"; slider.setMode(period.value === "day", period.value === "week" ? LIMIT_STEPS_WEEK : LIMIT_STEPS); };
  period.onchange = sync;
  sync();
  return {
    slider,
    el: h("div.plan", h("b", T("Internet budget and block times"), fieldInfo(T("Minutes from the shop or rewards come on top; the budget is used first and starts again at the reset."))),
      h("div.field-row", resetDayField, h("label.field", T("Reset at"), reset)),
      h("div.field", h("b", T("Block times"), fieldInfo(T("The internet is off – and you choose what Family Quest still allows."))), blockBox)),
    value: () => {
      const sv = slider.value(), bl = blocks.filter(b => b.days.length);
      if (sv.all === 0 && !Object.keys(sv.days).length && !bl.length) return null;      // no plan: only earned minutes
      return { budget: sv.all, period: period.value, reset: reset.value || "00:00", reset_day: +resetDay.value, days: sv.days, blocks: bl };
    },
  };
}

async function profileDialog(p, persons, role = "kid") {
  const isNew = !p;
  p = p || { name: "", role, color: role === "parent" ? "#495057" : "#4f8cff", settings: Object.assign({}, P.meta.profile_defaults), planer_person_id: null };
  const s = Object.assign({}, P.meta.profile_defaults, p.settings);
  const f = {
    name: h("input", { type: "text", value: p.name }),
    role: h("select", h("option", { value: "kid", selected: p.role === "kid" }, T("Child")), h("option", { value: "parent", selected: p.role === "parent" }, T("Parent"))),
    color: h("input", { type: "color", value: p.color }),
    pin: h("input", { type: "password", inputmode: "numeric", autocomplete: "new-password" }),
    daily_goal: h("input", { type: "number", min: 5, max: 1000, value: s.daily_goal }),
    lesson_length: h("input", { type: "number", min: 4, max: 40, value: s.lesson_length }),
    new_per_lesson: h("input", { type: "number", min: 0, max: 20, value: s.new_per_lesson }),
    learning_hours: h("input", { type: "text", placeholder: "07:00-20:00", value: s.learning_hours || "" }),
    auto_logout_min: h("input", { type: "number", min: 0, max: 240, value: s.auto_logout_min }),
    internet_entity: entitySelect(s.internet_entity, ["input_number", "number"]),
    internet_daily_limit: h("input", { type: "number", min: 0, max: 600, value: s.internet_daily_limit }),
    planer: h("select", h("option", { value: "" }, "–"), ...persons.map(x => h("option", { value: x.id, selected: x.id === p.planer_person_id }, x.name))),
    notify_service: h("input", { type: "text", placeholder: "notify.mobile_app_phone", value: s.notify_service || "", list: "notify-ents" }),
    internet_rule: entitySelect(s.internet_rule, ["switch", "input_boolean"]),
    internet_rule_blocks: h("input", { type: "checkbox", checked: s.internet_rule_blocks !== false }),
  };
  const ruleList = null;
  // budget entity: create a helper in Home Assistant with one click
  const createBudget = P.meta.ha ? h("button.btn.small.ghost", { type: "button", onclick: async () => {
    const name = I18N.tr(T("Internet minutes")) + " " + (f.name.value.trim() || "");
    try { const r = await call("parent/ha/input_number", { method: "POST", body: { name } }); f.internet_entity.setValue(r.entity_id); toast(T("Created in Home Assistant"), "good"); } catch {}
  } }, "➕ ", T("Create")) : null;
  const notifyList = h("datalist#notify-ents");
  if (P.meta.ha) call("parent/ha/entities?domain=notify").then(l => notifyList.replaceChildren(...l.map(e => h("option", { value: e.entity_id })))).catch(() => {});
  const ents = null;
  const plan = internetPlanEditor(s.internet_plan);
  // daily time: games, learning, internet – three sliders, each with its weekdays (children only)
  const gameLimit = limitSlider({ icon: "🎮", label: T("Games per day"), value: s.game_limit });
  const learnLimit = limitSlider({ icon: "📚", label: T("Learning per day"), value: s.learn_limit });
  const timePart = h("div.form.lim-box", h("h3", { "data-ik": "prof.time" }, "⏱️ ", T("Time per day")),
    gameLimit.el, learnLimit.el, plan.slider.el);
  const batteryPart = !isNew && p.role === "kid" ? kidBatteryBox(p.id) : null;
  const kidPart = h("div.form", h("h3", { "data-ik": "prof.internet" }, T("Internet minutes")),
    h("div.grid2", h("label.field", h("span", T("UniFi firewall rule (switch)"), fieldInfo(T("The child starts and stops the internet time in the app; the budget is the account «Internet minutes»."))), f.internet_rule, ruleList),
      h("label.check", f.internet_rule_blocks, T("The rule blocks the internet while the switch is on"))),
    h("div.grid2", h("label.field", h("span", T("Budget entity in Home Assistant"), fieldInfo(T("Receives the minutes from the shop, e.g. for your own automations."))), h("div.row", f.internet_entity, createBudget)),
      h("label.field", T("Maximum minutes per day from the shop"), f.internet_daily_limit)),
    plan.el);
  const parentPart = h("div.form", h("h3", { "data-ik": "prof.push" }, "🔔 ", T("Push messages")),
    h("label.field", T("Notify service of this parent"), f.notify_service, notifyList));
  // Home Assistant devices this profile may switch (light in the own room, …)
  const devSel = new Set(s.devices || []);
  const devSearch = h("input", { type: "search", placeholder: I18N.tr(T("Search …")) });
  const devList = h("div.dev-pick");
  const devPick = h("div", { hidden: true }, devSearch, devList);
  const devPills = h("div.dev-pills");
  let devNames = {};
  const drawPills = () => devPills.replaceChildren(...[...devSel].map(id => h("span.chip.dev-pill", { title: id, translate: "no" }, devNames[id] || id)),
    !devSel.size ? h("span.small.muted", T("No devices yet.")) : null,
    h("button.btn.small.ghost", { type: "button", onclick: () => { devPick.hidden = !devPick.hidden; if (!devPick.hidden) devSearch.focus(); } }, "✏️ ", T("Edit")));
  const devBox = h("div", devPills, devPick);
  drawPills();
  if (P.meta.ha) Promise.all([call("parent/ha/areas").then(l => l.map(a => ({ entity_id: "area." + a.area_id,
      name: "🏠 " + a.name + " · " + I18N.tr(T("whole room ({0} devices)")).replace("{0}", a.count) }))).catch(() => []),
    ...["light", "switch", "fan", "cover", "scene", "script", "input_boolean"].map(d => call("parent/ha/entities?domain=" + d).catch(() => []))])
    .then(lists => {
      const all = lists.flat();
      for (const e of all) devNames[e.entity_id] = e.name || e.entity_id;
      drawPills();
      // devices with the person's name on top (chosen ones first, lights before switches …), then other chosen ones, then the rest
      const DOM_ORDER = ["area", "light", "switch", "fan", "cover", "input_boolean", "scene", "script"];
      const rank = e => {
        const n = f.name.value.trim().toLowerCase(), txt = (e.name + " " + e.entity_id).toLowerCase();
        const dom = Math.max(0, DOM_ORDER.indexOf(e.entity_id.split(".")[0]));
        const match = n.length >= 2 && txt.includes(n), on = devSel.has(e.entity_id);
        return (match ? (on ? 0 : 100) : on ? 200 : 1000) + dom * 10;
      };
      const draw = () => { const q = devSearch.value.trim().toLowerCase();
        const list = all.filter(e => devSel.has(e.entity_id) || !q || (e.name + " " + e.entity_id).toLowerCase().includes(q))
          .map(e => [rank(e), e]).sort((a, b) => a[0] - b[0] || a[1].name.localeCompare(b[1].name, I18N.locale)).map(x => x[1]);
        devList.replaceChildren(...list.slice(0, 80).map(e =>
          h("label.check.dev", h("input", { type: "checkbox", checked: devSel.has(e.entity_id), onchange: ev => { ev.target.checked ? devSel.add(e.entity_id) : devSel.delete(e.entity_id); drawPills(); } }),
            C(e.name), h("span.small.muted.mono", " " + e.entity_id)))); };
      devSearch.oninput = draw; draw();
    });
  // avatar of this profile (not for a new one – it has no profile id yet)
  const avBox = h("div", h("p.small.muted", "…"));
  let avatar = null;
  if (!isNew) call(`parent/profiles/${p.id}/avatar`).then(d => { avatar = JSON.parse(JSON.stringify(d.avatar)); avBox.replaceChildren(avatarEditorBox(d, avatar)); }).catch(() => avBox.replaceChildren());
  // 🔐 Sign-in: one explicit choice per profile (profile setting «login», enforced by the server – db.login_mode):
  // 🪄 no sign-in (tap, children only) · 🔢 PIN · 🏠 Home Assistant only · 🔢🏠 PIN or Home Assistant.
  // The Home Assistant user shows only for the Home Assistant options, the PIN entry only for the PIN options.
  const hasHaLink = !!(p.settings && p.settings.ha_user_id);
  const haOk = () => !!(P.meta.ha || hasHaLink);          // without Home Assistant (and no link yet) the HA options are off
  let loginMode = p.login || (isNew ? (role === "parent" ? (P.meta.ha ? "ha" : "pin") : "none")
    : p.has_pin ? (hasHaLink ? "pin_ha" : "pin") : hasHaLink ? "ha" : (p.role === "parent" ? "pin" : "none"));
  const usesPin = () => loginMode === "pin" || loginMode === "pin_ha";
  const usesHa = () => loginMode === "ha" || loginMode === "pin_ha";
  const haUser = h("select", h("option", { value: "" }, "– " + I18N.tr(T("Choose a Home Assistant user")) + " –"),
    hasHaLink ? h("option", { value: p.settings.ha_user_id, selected: true, "data-name": p.settings.ha_user_name || "" }, p.settings.ha_user_name || p.settings.ha_user_id) : null);
  const haInfo = h("span.hint");
  if (P.meta.ha) call("parent/ha/users").then(list => {
    const cur = p.settings && p.settings.ha_user_id;
    haUser.replaceChildren(h("option", { value: "" }, "– " + I18N.tr(T("Choose a Home Assistant user")) + " –"), ...list.map(u => h("option", { value: u.id, selected: u.id === cur, "data-name": u.name },
      u.name + (u.linked_to && u.id !== cur ? " (" + u.linked_to + ")" : ""))));
    if (cur && !list.some(u => u.id === cur)) haUser.append(h("option", { value: cur, selected: true, "data-name": p.settings.ha_user_name || "" }, p.settings.ha_user_name || cur));
    if (!list.length) haInfo.textContent = I18N.tr(T("No Home Assistant user found – a user needs a person in Home Assistant (Settings › People)."));
  }).catch(() => {});
  // choosing a Home Assistant user: the name comes along (unless the parent typed one)
  let autoName = isNew ? "" : null;
  haUser.addEventListener("change", () => {
    const n = haUser.value ? haUser.selectedOptions[0]?.dataset.name || "" : "";
    if (n && (!f.name.value.trim() || f.name.value === autoName)) { f.name.value = n; autoName = n; }
  });
  let haKid = true;
  const haLabel = h("span");
  const haPart = h("div.login-sub", h("label.field", h("span", haLabel, fieldInfo(() => haKid
    ? T("Home Assistant sidebar and «Sign in with Home Assistant» on tablets – only the children's app, never the parent area.")
    : T("Home Assistant sidebar opens the parent area; on tablets «Sign in with Home Assistant»."))), haUser, haInfo));
  const syncHa = kid => {
    haKid = kid;
    haLabel.textContent = I18N.tr(kid ? T("Logs in to the children's app as") : T("Logs in to the parent area as"));
  };
  // PIN: children a picture PIN (4 symbols) or digits, parents digits – an existing PIN stays unless «Change PIN»
  const symbolKind = (p.settings && p.settings.pin_kind) === "symbols";
  let pinKind = p.has_pin ? (symbolKind && p.role !== "parent" ? "symbols" : "digits") : (p.role === "parent" ? "digits" : "symbols");
  let pad = null;
  const pinArea = h("div");
  const kindBtns = h("div.pin-kind");
  let changing = isNew || !p.has_pin;
  const pinForm = h("div.login-sub", kindBtns, pinArea);
  const drawPin = () => {
    const kid = f.role.value === "kid";
    if (!kid && pinKind === "symbols") pinKind = "digits";
    if (!changing) {
      kindBtns.replaceChildren();
      pinArea.replaceChildren(h("div.row",
        h("span.small.muted", "✓ " + I18N.tr(symbolKind && kid ? T("Picture PIN is set.") : T("Digit PIN is set."))),
        h("button.btn.small.ghost", { type: "button", onclick: () => { changing = true; drawPin(); } }, "🔑 ", T("Change PIN")),
        p.id ? logoutEverywhereBtn(p) : null));
      return;
    }
    kindBtns.replaceChildren(...(kid ? [["symbols", "🐱 " + I18N.tr(T("Symbols"))], ["digits", "🔢 " + I18N.tr(T("Digits"))]] : [])
      .map(([k, n]) => h("button.btn.small" + (pinKind === k ? "" : ".ghost"), { type: "button", onclick: () => { pinKind = k; pad = null; drawPin(); } }, n)));
    if (pinKind === "symbols") pinArea.replaceChildren(pad = pad || symbolPad({ mode: "set", cancel: false }));
    else pinArea.replaceChildren(h("label.field", p.has_pin ? T("New PIN") : "PIN", f.pin, h("span.hint", kid ? T("4 digits") : T("4–8 digits"))));
  };
  const LOGIN_OPTS = [
    ["none", "🪄", T("No sign-in – tap the profile"), () => T("The child taps its picture and is in – no PIN, no Home Assistant.")],
    ["pin", "🔢", T("PIN"), kid => kid ? T("A picture PIN or a 4-digit PIN – on every device.") : T("A digit PIN (4–8 digits) – in the app and the parent area.")],
    ["ha", "🏠", T("Home Assistant only"), () => T("Only with the linked Home Assistant user (sidebar, «Sign in with Home Assistant» on tablets) – no PIN.")],
    ["pin_ha", "🔢🏠", T("PIN or Home Assistant"), () => T("Both ways: the PIN on any device, or the linked Home Assistant user.")],
  ];
  const loginList = h("div.login-opts", { role: "radiogroup" });
  const loginHint = h("p.small.muted");
  const loginForm = h("div.form.login-box", h("h3", { "data-ik": "prof.login" }, "🔐 ", T("Sign-in")), loginList, loginHint, haPart, pinForm);
  const drawLogin = () => {
    const kid = f.role.value === "kid";
    if (!kid && loginMode === "none") loginMode = "pin";          // parents always sign in
    if (!haOk() && usesHa()) loginMode = kid ? "none" : "pin";
    loginList.replaceChildren(...LOGIN_OPTS.filter(o => kid || o[0] !== "none").map(([k, icon, label, expl]) => {
      const off = (k === "ha" || k === "pin_ha") && !haOk();
      return h("label.login-opt" + (loginMode === k ? ".on" : "") + (off ? ".off" : ""),
        h("input", { type: "radio", name: "fq-login", value: k, checked: loginMode === k, disabled: off,
          onchange: () => { loginMode = k; drawLogin(); } }),
        h("span.login-ic", { "aria-hidden": "true" }, icon),
        h("span.login-txt", h("strong", label), h("span.small.muted", expl(kid))));
    }));
    loginHint.textContent = !haOk() ? I18N.tr(T("Home Assistant is not connected – the Home Assistant options need it.")) : "";
    loginHint.hidden = !loginHint.textContent;
    haPart.hidden = !usesHa();
    pinForm.hidden = !usesPin();
    drawPin();
  };
  // the dialog in parts (tabs): profile · learning · time & battery · internet & devices – Save / Cancel always at the bottom,
  // «Remove» set apart at the end of the profile tab
  const danger = !isNew && p.id !== P.meta.me.id ? h("div.danger-zone", h("h3", { "data-ik": "Remove profile" }, "⚠️ ", T("Remove profile")),
    h("p.small.muted", T("Archive the profile or delete it for good – you confirm it in the next step.")),
    h("button.btn.small.bad", { type: "button", onclick: remove }, "🗑 ", T("Remove"))) : null;
  const tabs = tabbed([
    { key: "profile", label: "👤 " + I18N.tr(T("Profile")), content: [
      h("div.grid2", h("label.field", T("Name"), f.name), h("label.field", T("Role"), f.role), h("label.field", T("Colour"), f.color)),
      loginForm,
      isNew ? null : h("div.form", h("h3", { "data-ik": "prof.avatar" }, "🧑‍🎨 ", T("Avatar")), avBox),
      persons.length ? h("label.field", h("span", T("Person in the Family Planer"), fieldInfo(T("Shows the chores of this person and counts them."))), f.planer) : null,
      parentPart, danger] },
    { key: "learn", label: "📚 " + I18N.tr(T("Learning")), content: [
      h("h3", { "data-ik": "prof.learn" }, "📚 ", T("Learning")),
      h("div.field-row", h("label.field", T("Daily goal (XP)"), f.daily_goal), h("label.field", T("Exercises per lesson"), f.lesson_length),
        h("label.field", T("New cards per lesson"), f.new_per_lesson),
        h("label.field", h("span", T("Learning hours"), fieldInfo(T("Empty = always. Example: 07:00-20:00"))), f.learning_hours),
        h("label.field", h("span", T("Log out after minutes without touch"), fieldInfo(T("0 = never"))), f.auto_logout_min))] },
    { key: "time", label: "⏱️ " + I18N.tr(T("Time & battery")), content: [timePart, batteryPart] },
    { key: "net", label: "🌐 " + I18N.tr(T("Internet & devices")), content: [kidPart, P.meta.ha ? h("div.form", h("h3", { "data-ik": "prof.devices" }, "🏠 ", T("Devices")), devBox) : null] },
  ]);
  const syncRole = () => {
    const kid = f.role.value === "kid";
    kidPart.hidden = timePart.hidden = !kid; if (batteryPart) batteryPart.hidden = !kid; parentPart.hidden = kid; syncHa(kid);
    tabs.setVisible("time", kid); tabs.setVisible("net", kid || !!P.meta.ha);
    drawLogin();
  };
  f.role.addEventListener("change", syncRole); syncRole();
  const m = modal(h("div.form.profile-dlg",
    h("h2", isNew ? (p.role === "parent" ? T("New parent") : T("New child")) : T("Edit profile")),
    tabs.el,
    h("div.dlg-foot", h("button.btn", { onclick: save }, T("Save")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))), { wide: true });
  const focusIn = el => { tabs.reveal(el); el.focus(); };
  async function save() {
    // the sign-in decides what is sent: the PIN only for the PIN options, the Home Assistant user only for the HA options
    let pin = null, pinSymbols;
    if (usesPin() && changing) {
      if (pinKind === "symbols") {
        const v = pad && pad.value();
        if (!v || v.symbols.length !== 4) { tabs.show("profile"); return toast(T("Choose 4 symbols"), "bad"); }
        pinSymbols = v;
      } else {
        pin = f.pin.value || null;
        if (!pin) { focusIn(f.pin); return toast(p.has_pin ? T("Enter the new digit PIN") : T("Set a PIN for this sign-in"), "bad"); }
      }
    }
    if (usesHa() && !haUser.value) { focusIn(haUser); return toast(T("Choose the Home Assistant user for this sign-in"), "bad"); }
    const isParent = f.role.value === "parent";
    const body = { name: f.name.value, role: f.role.value, color: f.color.value, pin, planer_person_id: f.planer.value || null, login: loginMode,
      ha_user_id: usesHa() ? haUser.value : "", ha_user_name: usesHa() ? haUser.selectedOptions[0]?.dataset.name || "" : "",
      ...(pinSymbols ? { pin_symbols: pinSymbols.symbols, symbol_set: pinSymbols.set } : {}),
      settings: { daily_goal: +f.daily_goal.value, lesson_length: +f.lesson_length.value, new_per_lesson: +f.new_per_lesson.value,
        learning_hours: f.learning_hours.value.trim(), auto_logout_min: +f.auto_logout_min.value, internet_entity: f.internet_entity.value,
        internet_daily_limit: +f.internet_daily_limit.value, notify_service: f.notify_service.value.trim(),
        internet_rule: f.internet_rule.value, internet_rule_blocks: f.internet_rule_blocks.checked, internet_plan: plan.value(),
        ...(isParent ? {} : { game_limit: gameLimit.value(), learn_limit: learnLimit.value() }),
        ...(P.meta.ha ? { devices: [...devSel] } : {}) } };
    const saved = await call(isNew ? "parent/profiles" : `parent/profiles/${p.id}`, { method: isNew ? "POST" : "PUT", body });
    if (saved && saved.parent_token) Auth.parent = saved.parent_token;
    if (avatar) await call(`parent/profiles/${p.id}/avatar`, { method: "PUT", body: { avatar } });
    m.close(); toast(T("Saved"), "good"); render();
  }
  function remove() { removeDialog(p, false, () => m.close()); }
}

// ---------------------------------------------------------------- behaviour weather
const WEATHER_NAMES = [T("Sunny"), T("Cloudy"), T("Rain"), T("Thunderstorm")];   // default names (translated)
const WEATHER_ICONS = ["☀️", "🌤️", "⛅", "🌥️", "☁️", "🌦️", "🌧️", "⛈️", "🌩️", "🌨️", "❄️", "🌪️", "🌫️", "🌈", "🌙", "⭐"];
const wName = n => n ? I18N.tr(n) : "";
function weatherColor(rank, n) {
  const pal = ["#f7b801", "#9bc53d", "#adb5bd", "#4d96ff", "#6c4ab6", "#c1121f"];
  return pal[Math.round(rank / Math.max(1, n - 1) * (pal.length - 1))];
}
function weatherGraph(days, n) {
  const W = 300, H = 46, bw = W / days.length;
  const svg = (t, a, ...c) => { const e = document.createElementNS("http://www.w3.org/2000/svg", t); for (const k in a) e.setAttribute(k, a[k]); e.append(...c); return e; };
  const bars = days.map((d, i) => {
    const x = i * bw + 1, w = Math.max(2, bw - 2);
    const title = svg("title", {}, new Date(d.date).toLocaleDateString(I18N.locale, { weekday: "short", day: "numeric", month: "short" }) + (d.icon ? " " + d.icon : " –"));
    if (d.rank == null) return svg("rect", { x, y: H - 3, width: w, height: 3, rx: 1, fill: "currentColor", opacity: .18 }, title);
    const hh = 6 + (H - 8) * (n - 1 - Math.min(d.rank, n - 1)) / Math.max(1, n - 1);
    return svg("rect", { x, y: H - hh, width: w, height: hh, rx: 2, fill: weatherColor(Math.min(d.rank, n - 1), n) }, title);
  });
  return svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "weather-graph", preserveAspectRatio: "none", role: "img", "aria-label": I18N.tr(T("Weather of the last 30 days")) }, ...bars);
}

/** Behaviour weather: part "set" (today's weather per child – in the overview) or "config" (in the settings). */
async function weatherView(main, part = "both") {
  const d = await call("parent/weather");
  if (!P.accounts.length) P.accounts = await call("parent/accounts");
  const cfg = d.config, n = cfg.levels.length;
  const list = section("⛅ " + I18N.tr(T("Weather of the day")),
    h("p.muted", I18N.tr(T("Everybody is back at {0} at {1}.")).replace("{0}", cfg.levels.find(l => l.key === cfg.default)?.icon || "").replace("{1}", cfg.reset)),
    !cfg.enabled ? h("p.bad", T("The weather is switched off.")) : null,
    !d.kids.length ? h("p.muted", T("No children yet.")) : null,
    h("ul.weather-list", ...d.kids.map(k => {
      const li = h("li.weather-row");
      const draw = (cur, days) => {
        const counts = {};
        days.forEach(x => { if (x.icon) counts[x.icon] = (counts[x.icon] || 0) + 1; });
        li.replaceChildren(
          h("div.row.weather-who", avatarSvg(k.profile.avatar, 44), C(k.profile.name, "strong.grow"),
            cur ? h("span.weather-now", { title: wName(cur.name) }, cur.icon) : null),
          h("div.weather-btns", ...cfg.levels.map(l => h("button.btn.small" + (cur && cur.key === l.key ? ".on" : ".ghost"), {
            disabled: !cfg.enabled, title: wName(l.name),
            onclick: async () => {
              try {
                const r = await call(`parent/weather/${k.profile.id}`, { method: "POST", body: { level: l.key } });
                toast(l.icon + " " + k.profile.name + (l.points ? " · " + (l.points > 0 ? "+" : "") + fmt(l.points) : ""), l.points < 0 ? "" : "good");
                draw(r.current, r.days);
              } catch (e) { toast(e.message, "bad"); }
            } }, h("span.big-ic", l.icon), l.points ? h("span.small", (l.points > 0 ? " +" : " ") + fmt(l.points)) : null))),
          h("div.weather-hist", weatherGraph(days, n),
            h("div.small.muted.row", h("span.grow", T("Last 30 days")),
              ...cfg.levels.filter(l => counts[l.icon]).map(l => h("span", l.icon + " " + counts[l.icon])))));
      };
      draw(k.current, k.days);
      return li;
    })));

  // ---- configuration
  let lastIcon = null;
  const rows = h("div.weather-cfg");
  const addRow = l => {
    const icon = h("input.weather-icon", { type: "text", value: l.icon || "", maxlength: 8, onfocus: () => { lastIcon = icon; } });
    const name = h("input.grow", { type: "text", value: wName(l.name), placeholder: I18N.tr(T("Name")) });
    const pts = h("input", { type: "number", step: "1", value: l.points ?? 0 });
    const row = h("div.row.weather-cfg-row", icon, name, pts, h("span.small.muted", T("points")),
      h("button.icon-btn", { title: T("Up"), onclick: () => row.previousElementSibling && rows.insertBefore(row, row.previousElementSibling) }, "▲"),
      h("button.icon-btn", { title: T("Delete"), onclick: () => row.remove() }, "🗑"));
    row.read = () => ({ key: l.key, icon: icon.value.trim(), points: Number(pts.value || 0),
      // keep the English source name when the parent did not change the translated one – it stays translated
      name: name.value.trim() === wName(l.name) ? l.name : name.value.trim() });
    rows.append(row);
    if (!l.icon) lastIcon = icon;
  };
  cfg.levels.forEach(addRow);
  const palette = h("div.row.weather-palette", ...WEATHER_ICONS.map(ic => h("button.icon-btn", { onclick: () => { if (lastIcon) lastIcon.value = ic; } }, ic)));
  const def = h("select", ...cfg.levels.map(l => h("option", { value: l.key, selected: l.key === cfg.default }, l.icon + " " + wName(l.name))));
  const time = h("input", { type: "time", value: cfg.reset });
  const acc = h("select", ...P.accounts.filter(a => a.active && a.key !== "xp").map(a => h("option", { value: a.key, selected: a.key === cfg.account }, a.icon + " " + I18N.tr(a.name))));
  const on = h("input", { type: "checkbox", checked: cfg.enabled });
  const conf = section("☀️ " + I18N.tr(T("Bonus/malus points")),
    rows, h("div.row", h("button.btn.small.ghost", { onclick: () => addRow({ icon: "", name: "", points: 0 }) }, "＋ ", T("Add weather"))),
    h("div.small.muted", T("Tap a symbol to put it into the field you edited last:")), palette,
    h("div.grid3", h("label.field", h("span", T("Reset every day at")), time),
      h("label.field", h("span", T("After the reset everybody has")), def),
      h("label.field", h("span", T("Book the points on")), acc)),
    h("label.row", on, " ", T("Use the weather")),
    h("div.row", h("button.btn", { onclick: async () => {
      try {
        await call("parent/weather/config", { method: "PUT", body: { enabled: on.checked, levels: [...rows.children].map(r => r.read()),
          default: def.value, reset: time.value || "12:00", account: acc.value } });
        toast(T("Saved"), "good"); render();
      } catch (e) { toast(e.message, "bad"); }
    } }, T("Save"))));
  if (part === "set" && !cfg.enabled) return;
  main.append(...(part === "config" ? [conf] : part === "set" ? [list] : [list, conf]));
}

const KID_OPEN = new Set();               // overview: the children's rows that are open (while the page lives)

/** The weather of the day of one child (overview row): the symbol now, the buttons to pick it, the last 30 days. */
function kidWeather(k, cfg) {
  const now = h("span.weather-now"), pick = h("div.weather-btns"), hist = h("div.weather-hist");
  const back = cfg.levels.find(l => l.key === cfg.default);
  const info = fieldInfo(() => [T("Give each child its weather – the bonus or malus is booked right away. Only the child sees its own weather."),
    I18N.tr(T("Everybody is back at {0} at {1}.")).replace("{0}", back ? back.icon : "").replace("{1}", cfg.reset)], { title: T("Weather of the day") });
  const draw = (cur, days) => {
    now.textContent = cur ? cur.icon : ""; now.title = cur ? wName(cur.name) : "";
    const counts = {};
    days.forEach(x => { if (x.icon) counts[x.icon] = (counts[x.icon] || 0) + 1; });
    pick.replaceChildren(h("span.small.muted.weather-lbl", T("Today's weather:"), info), ...cfg.levels.map(l => h("button.btn.small" + (cur && cur.key === l.key ? ".on" : ".ghost"), { type: "button", title: wName(l.name),
      onclick: async () => {
        try {
          const r = await call(`parent/weather/${k.profile.id}`, { method: "POST", body: { level: l.key } });
          toast(l.icon + " " + k.profile.name + (l.points ? " · " + (l.points > 0 ? "+" : "") + fmt(l.points) : ""), l.points < 0 ? "" : "good");
          draw(r.current, r.days);
        } catch (e) { toast(e.message, "bad"); }
      } }, h("span.big-ic", l.icon), l.points ? h("span.small", (l.points > 0 ? " +" : " ") + fmt(l.points)) : null)));
    if (!days.some(x => x.icon)) return hist.replaceChildren(h("p.muted.small", T("No weather recorded yet – pick one above.")));
    hist.replaceChildren(weatherGraph(days, cfg.levels.length), h("div.small.muted.row", h("span.grow", T("Last 30 days")),
      ...cfg.levels.filter(l => counts[l.icon]).map(l => h("span", l.icon + " " + counts[l.icon]))));
  };
  draw(k.current, k.days);
  return { now, pick, hist };
}

/** «Log out everywhere»: every login of this profile ends on every device (app, parent area, planner). */
function logoutEverywhereBtn(p) {
  return h("button.btn.small.ghost", { type: "button", onclick: async () => {
    if (!(await confirmDialog(I18N.tr(T("Log {0} out on all devices?")).replace("{0}", p.name)))) return;
    try {
      const r = await call("parent/sessions/end", { method: "POST", body: { profile_id: p.id } });
      if (r.parent_token) Auth.parent = r.parent_token;          // the own profile: this device stays signed in
      toast(T("Signed out on all devices"), "good");
    } catch (e) { /* call() shows the error */ }
  } }, "🚪 ", T("Log out everywhere"));
}
