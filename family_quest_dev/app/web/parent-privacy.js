// ---------------------------------------------------------------- 🛡️ Privacy (parent area): retention periods, clean-up runs, past runs
// Backend: familyquest/privacy.py, api/privacy.py. The clean-up list IS the preview (a dry run): nothing is deleted until
// the parents confirm. Every run writes a backup snapshot first, deletes each kind in one transaction and is logged.
// Own CSS block below (class prefix «pv-»); the ⓘ texts join PARENT_INFO (parent-info.js).

Object.assign(PARENT_INFO, {
  [T("Privacy")]: [
    T("How long Family Quest keeps each kind of personal data, and the clean-up runs that delete what is older. Nothing is deleted without you, unless you switch on the automatic clean-up at night."),
    T("Balances, levels and XP never change: old bookings are added up into one «Balance brought forward»."),
    T("Older copies can still be in your backups and in the history of Home Assistant. Delete old backups too if the data should be gone everywhere.")],
  [T("Retention periods")]: [
    T("For every kind of stored data: how long it is kept – days, months, years or «keep forever». The defaults are a sensible start; change them as you like."),
    T("What the family made itself (books, quizzes, decks, photo sets, profiles, balances, settings) is not time-based: it is kept until you delete it where it lives.")],
  [T("Clean-up runs")]: [
    T("What is past its retention period, by kind, with the number of entries and the oldest and newest date. This list is the preview – nothing is deleted yet."),
    T("Choose kinds (or single entries) and delete them. Before every run a backup snapshot is written to the data folder (privacy_backups, the last 3 are kept). Each kind is deleted in one transaction."),
    T("Never deleted because it is still in use: anything of the current week, running games, open and pending chores, open deals, orders waiting for approval, open topics and polls, upcoming events and gift draws, the days of a running streak, the bookings since the active family goal started, the newest entry of every list.")],
  [T("Past runs")]: T("The clean-up runs so far: when, who (or the automatic run at night), what and how many entries, and the snapshot written before."),
  "pv.keep": T("How long each kind of data is kept before it is due for a clean-up."),
  "pv.clean": T("Deleting what is past its retention period – by hand or automatically at night – and the log of the runs so far."),
  [T("Delete all data of a child")]: T("To remove everything of one child at once, delete its profile for good: profile, points, progress, history, books and programs. Archive keeps the data and only hides the profile."),
});

(() => {
  const css = `
.pv-hint { display: flex; gap: 10px; align-items: flex-start; padding: 10px 12px; border-radius: 12px; background: var(--hover); margin: 0 0 12px; }
.pv-hint p { margin: 0; }
.pv-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.pv-row { display: grid; grid-template-columns: 30px minmax(0, 1fr) auto; gap: 8px; align-items: center; padding: 8px 10px; border: 1px solid var(--line); border-radius: 12px; background: var(--card); }
.pv-row .pv-ic { font-size: 1.35rem; text-align: center; }
.pv-row .pv-name { font-weight: 700; min-width: 0; overflow-wrap: anywhere; }
.pv-row .pv-sub { display: block; font-weight: 400; color: var(--muted); font-size: .85rem; }
.pv-period { display: flex; gap: 6px; align-items: center; }
.pv-period input { width: 64px; }
.pv-period select { min-width: 0; }
.pv-row.pv-keep { background: transparent; border-style: dashed; }
.pv-chip-keep { background: var(--good-bg); color: var(--good-text); }
.pv-due { grid-template-columns: 26px 30px minmax(0, 1fr) auto; }
.pv-due input[type=checkbox] { width: 20px; height: 20px; margin: 0; accent-color: var(--accent); }
.pv-count { font-weight: 800; font-variant-numeric: tabular-nums; white-space: nowrap; }
.pv-drill { grid-column: 1 / -1; margin-top: 4px; }
.pv-entries { list-style: none; margin: 6px 0 0; padding: 0; max-height: 260px; overflow: auto; border-top: 1px solid var(--line); }
.pv-entries li { display: flex; gap: 8px; align-items: center; padding: 5px 2px; border-bottom: 1px solid var(--line); font-size: .9rem; }
.pv-entries li .pv-when { color: var(--muted); white-space: nowrap; font-variant-numeric: tabular-nums; }
.pv-entries li .pv-lbl { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pv-bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 12px; }
.pv-bar .grow { flex: 1; }
.pv-auto { display: flex; gap: 12px; align-items: center; padding: 10px 0 2px; }
.pv-runs li { display: grid; grid-template-columns: minmax(0, 1fr); gap: 2px; padding: 8px 0; border-bottom: 1px solid var(--line); }
.pv-runs li:last-child { border-bottom: 0; }
.pv-confirm ul { margin: 6px 0 10px; padding-left: 20px; }
.pv-kids { display: flex; flex-wrap: wrap; gap: 8px; }
.pv-master { display: flex; gap: 12px; align-items: center; }
.pv-off { opacity: .55; }
.pv-badge { margin-left: auto; min-width: 22px; height: 22px; padding: 0 7px; border-radius: 11px; background: var(--bad); color: #fff;
  font-size: .75rem; font-weight: 800; line-height: 22px; text-align: center; font-variant-numeric: tabular-nums; flex: none; }
.mob-menu { position: relative; }
.pv-dot { position: absolute; top: 4px; right: 4px; width: 10px; height: 10px; border-radius: 50%; background: var(--bad); box-shadow: 0 0 0 2px var(--card); }
@media (max-width: 560px) {
  .pv-row:not(.pv-due) { grid-template-columns: 30px minmax(0, 1fr); }
  .pv-row:not(.pv-due) > .pv-period, .pv-row:not(.pv-due) > .chip { grid-column: 2; justify-self: start; }
}`;
  document.head.append(h("style", { id: "pv-css" }, css));
})();

// ---- the red badge on the menu item «Privacy»: entries ready for a clean-up run (GET parent/privacy/badge, cached on the
// server a few minutes). Painted again whenever the menu is drawn anew; fetched at the start, every 5 minutes, after a run
// and after a settings change. The ☰ button on phones gets a red dot.
const PV_BADGE = { n: 0 };
const pvFmt = n => n > 999 ? "999+" : String(n);
function pvPaint() {
  const btn = document.querySelector('nav.side button[data-tab="privacy"]');
  if (btn) {
    let b = btn.querySelector(".pv-badge");
    if (!PV_BADGE.n) { if (b) b.remove(); }
    else {
      if (!b) btn.append(b = h("span.pv-badge", { translate: "no" }));
      if (b.textContent !== pvFmt(PV_BADGE.n)) b.textContent = pvFmt(PV_BADGE.n);
      const label = I18N.tr(T("{0} entries ready for a clean-up run")).replace("{0}", fmt(PV_BADGE.n));
      if (b.title !== label) { b.title = label; b.setAttribute("aria-label", label); }
    }
  }
  const mob = document.querySelector(".mob-menu");
  if (mob) { const d = mob.querySelector(".pv-dot"); if (!PV_BADGE.n && d) d.remove(); else if (PV_BADGE.n && !d) mob.append(h("span.pv-dot")); }
}
async function pvBadgeRefresh() {
  if (!Auth.parent) return;
  try { const r = await call("parent/privacy/badge"); PV_BADGE.n = r.on ? r.count : 0; } catch (e) { return; }
  pvPaint();
}
(() => {
  let pending = false;
  new MutationObserver(() => { if (!pending) { pending = true; requestAnimationFrame(() => { pending = false; pvPaint(); }); } })
    .observe(document.documentElement, { childList: true, subtree: true });
  setTimeout(pvBadgeRefresh, 1500);
  setInterval(pvBadgeRefresh, 5 * 60 * 1000);
})();

const PV_UNITS = [["days", T("days")], ["months", T("months")], ["years", T("years")], ["forever", T("keep forever")]];
const pvPeriod = p => p.unit === "forever" ? I18N.tr(T("keep forever"))
  : I18N.tr(p.n === 1 ? { days: T("1 day"), months: T("1 month"), years: T("1 year") }[p.unit]
    : { days: T("{0} days"), months: T("{0} months"), years: T("{0} years") }[p.unit]).replace("{0}", fmt(p.n));

async function privacyView(main) {
  const d = await call("parent/privacy");
  const kids = (P.profiles && P.profiles.length ? P.profiles : await call("parent/profiles").catch(() => [])).filter(p => p.role === "kid");
  const sel = new Set(), picks = {};            // chosen kinds; kind → Set of chosen entries (none = all of the kind)
  const kindsDue = d.kinds.filter(k => k.count > 0);

  // ---- retention periods
  const edits = {};
  const periodRow = k => {
    const n = h("input", { type: "number", min: 1, max: 3650, step: 1, value: k.retention.unit === "forever" ? k.default.n || 1 : k.retention.n,
      "aria-label": I18N.tr(T("Number")), disabled: k.retention.unit === "forever" });
    const u = h("select", { "aria-label": I18N.tr(T("Unit")) }, ...PV_UNITS.map(([v, t]) => h("option", { value: v, selected: v === k.retention.unit }, t)));
    const upd = () => { n.disabled = u.value === "forever"; edits[k.key] = { n: +n.value || 1, unit: u.value }; saveBtn.disabled = false; };
    n.oninput = upd; u.onchange = upd;
    return h("li.pv-row", { "data-kind": k.key }, h("span.pv-ic", k.icon),
      h("span.pv-name", k.title, " ", fieldInfo(k.info, { title: k.title }),
        h("span.pv-sub", I18N.tr(T("Default: {0}")).replace("{0}", pvPeriod(k.default)))),
      h("span.pv-period", n, u));
  };
  const saveBtn = h("button.btn", { disabled: true, onclick: async () => {
    await call("parent/privacy/settings", { method: "PUT", body: { retention: edits } });
    toast(T("Saved"), "good"); pvBadgeRefresh(); render();
  } }, "💾 ", T("Save"));
  const resetBtn = h("button.btn.ghost", { onclick: async () => {
    if (!await confirmDialog(T("Set every retention period back to its default?"))) return;
    await call("parent/privacy/settings", { method: "PUT", body: { retention: Object.fromEntries(d.kinds.map(k => [k.key, k.default])) } });
    toast(T("Saved"), "good"); pvBadgeRefresh(); render();
  } }, "↺ ", T("Defaults"));
  const retention = section("⏳ " + I18N.tr(T("Retention periods")),
    d.enabled ? null : h("p.small.muted", "⏸️ ", T("Privacy is switched off: nothing is counted or deleted. You can still edit the periods.")),
    h("ul.pv-list", ...d.kinds.map(periodRow),
      ...d.keep.map(k => h("li.pv-row.pv-keep", h("span.pv-ic", k.icon), h("span.pv-name", k.title, " ", fieldInfo(k.info, { title: k.title })),
        h("span.chip.pv-chip-keep", "♾️ ", T("Keep"))))),
    h("div.pv-bar", h("span.grow"), resetBtn, saveBtn));

  // ---- clean-up runs (the preview)
  const runBtn = h("button.btn.bad", { disabled: true, onclick: () => confirmRun() });
  const allBox = h("input", { type: "checkbox", "aria-label": I18N.tr(T("Select all")) });
  const total = () => kindsDue.filter(k => sel.has(k.key)).reduce((s, k) => s + (picks[k.key] && picks[k.key].size ? picks[k.key].size : k.count), 0);
  const sync = () => {
    const n = total();
    runBtn.disabled = !n;
    runBtn.textContent = "🗑 " + I18N.tr(T("Delete {0} entries")).replace("{0}", fmt(n));
    allBox.checked = kindsDue.length > 0 && kindsDue.every(k => sel.has(k.key));
    allBox.indeterminate = !allBox.checked && sel.size > 0;
    boxes.forEach((b, key) => { b.checked = sel.has(key); });
  };
  const boxes = new Map();
  const dueRow = k => {
    const box = h("input", { type: "checkbox", "aria-label": k.title, onchange: e => { e.target.checked ? sel.add(k.key) : sel.delete(k.key); if (!e.target.checked) delete picks[k.key]; sync(); } });
    boxes.set(k.key, box);
    const drill = h("div.pv-drill");
    const drillBtn = k.drill ? h("button.btn.small.ghost", { onclick: async () => {
      if (drill.childNodes.length) { drill.replaceChildren(); return; }
      const list = await call(`parent/privacy/entries/${k.key}`);
      const chosen = picks[k.key] || new Set();
      drill.replaceChildren(h("ul.pv-entries", ...list.map(e => h("li",
        h("input", { type: "checkbox", checked: chosen.has(e.id), "aria-label": e.label || e.at, onchange: ev => {
          ev.target.checked ? chosen.add(e.id) : chosen.delete(e.id);
          picks[k.key] = chosen;
          if (chosen.size) sel.add(k.key); else { sel.delete(k.key); delete picks[k.key]; }
          sync();
        } }),
        h("span.pv-when", fmtDate(e.at)), C(e.label, "span.pv-lbl")))),
        list.length < k.count ? h("p.small.muted", I18N.tr(T("The newest {0} are shown.")).replace("{0}", fmt(list.length))) : null,
        h("p.small.muted", T("Without single entries ticked, the whole kind is deleted.")));
    } }, "🔎 ", T("Single entries")) : null;
    return h("li.pv-row.pv-due", { "data-kind": k.key }, box, h("span.pv-ic", k.icon),
      h("span.pv-name", k.title, h("span.pv-sub",
        I18N.tr(T("{0} to {1}")).replace("{0}", fmtDate(k.oldest)).replace("{1}", fmtDate(k.newest)), " · ",
        I18N.tr(T("older than {0}")).replace("{0}", pvPeriod(k.retention)))),
      h("span.pv-count", fmt(k.count)), drillBtn ? h("div.pv-drill", drillBtn, drill) : null);
  };
  allBox.onchange = () => { kindsDue.forEach(k => allBox.checked ? sel.add(k.key) : (sel.delete(k.key), delete picks[k.key])); sync(); };
  const autoSw = h("input", { type: "checkbox", role: "switch", checked: d.auto, "aria-label": I18N.tr(T("Automatic clean-up at night")), onchange: async e => {
    await call("parent/privacy/settings", { method: "PUT", body: { auto: e.target.checked } });
    toast(e.target.checked ? T("Automatic clean-up switched on") : T("Automatic clean-up switched off"), "good");
  } });
  const cleanup = !d.enabled ? section("🧹 " + I18N.tr(T("Clean-up runs")), h("p.muted", "⏸️ ", T("Switched off – no clean-up runs, manual or automatic.")))
    : section("🧹 " + I18N.tr(T("Clean-up runs")),
    h("div.pv-hint", h("span", "💾"), h("p.small", I18N.tr(T("Before every run a backup snapshot is saved in the data folder ({0}, the last {1} are kept). Nothing is deleted until you confirm."))
      .replace("{0}", d.backup_dir).replace("{1}", d.keep_backups))),
    kindsDue.length ? [
      h("label.check.pv-all", allBox, T("Select all")),
      h("ul.pv-list", ...kindsDue.map(dueRow)),
      h("div.pv-bar", h("span.small.muted.grow", T("Entries still in use are never shown here.")), runBtn)]
      : h("p.muted", "✅ ", T("Nothing is past its retention period.")),
    h("div.pv-auto", h("label.switch-wrap", autoSw, h("span.switch-ui")),
      h("div.grow", h("strong", T("Automatic clean-up at night")),
        h("div.small.muted", I18N.tr(T("Every night between {0}:00 and {1}:00 the kinds past their period are cleaned, with a snapshot and an entry in the past runs. Off by default."))
          .replace("{0}", String(d.auto_hours[0]).padStart(2, "0")).replace("{1}", String(d.auto_hours[1]).padStart(2, "0"))))));
  sync();

  async function confirmRun() {
    const chosen = kindsDue.filter(k => sel.has(k.key));
    const go = h("button.btn.bad", { autofocus: true, onclick: async () => {
      go.disabled = true;
      try {
        const body = { kinds: chosen.map(k => k.key), entries: Object.fromEntries(Object.entries(picks).map(([k, s]) => [k, [...s]])) };
        const r = await call("parent/privacy/run", { method: "POST", body });
        m.close(); pvBadgeRefresh();
        toast(I18N.tr(T("{0} entries deleted")).replace("{0}", fmt(Object.values(r.counts).filter(n => n > 0).reduce((a, b) => a + b, 0))), "good");
        render();
      } catch (e) { go.disabled = false; toast(e.message, "bad"); }
    } }, "🗑 ", T("Delete now"));
    const m = modal(h("div.form.pv-confirm",
      h("h2", "⚠️ ", T("Delete old data?")),
      h("ul", ...chosen.map(k => h("li", k.icon, " ", k.title, ": ", h("strong", fmt(picks[k.key] && picks[k.key].size ? picks[k.key].size : k.count))))),
      h("p.small", "💾 ", T("A backup snapshot is written first. Each kind is deleted in one transaction; balances, levels and XP stay the same.")),
      h("p.small.muted", T("This cannot be undone in the app – only by restoring the snapshot.")),
      h("div.row", go, h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  }

  // ---- past runs
  const KT = Object.fromEntries(d.kinds.map(k => [k.key, k]));
  const past = section("🗂️ " + I18N.tr(T("Past runs")), d.runs.length ? h("ul.pv-list.pv-runs", ...d.runs.map(r => h("li",
    h("strong", fmtDateTime(r.at), " · ", r.auto ? I18N.tr(T("automatic")) : C(r.by_name || "?")),
    h("span.small", ...Object.entries(r.counts).flatMap(([k, n], i) => [i ? " · " : "", (KT[k] ? KT[k].icon + " " : ""), KT[k] ? h("span", KT[k].title) : k, " ",
      n < 0 ? h("span", { style: { color: "var(--bad-text)" } }, T("failed")) : h("strong", fmt(n))])),
    r.backup ? h("span.small.muted", "💾 ", C(r.backup)) : null))) : h("p.muted", T("No clean-up so far.")));

  // ---- one child: the guarded profile delete that exists already
  const child = kids.length ? section("👤 " + I18N.tr(T("Delete all data of a child")),
    h("p.small.muted", T("This uses the protected «Remove profile» dialog: type the name, choose «Delete for good».")),
    h("div.pv-kids", ...kids.map(p => h("button.btn.small.ghost", { onclick: () => removeDialog(p) }, avatarSvg(p.avatar, 22), " ", C(p.name))))) : null;

  // the master switch: off = nothing is counted, no runs (manual or automatic), no badge
  const master = h("input", { type: "checkbox", role: "switch", checked: d.enabled, "aria-label": I18N.tr(T("Privacy clean-up")), onchange: async e => {
    await call("parent/privacy/settings", { method: "PUT", body: { enabled: e.target.checked } });
    toast(e.target.checked ? T("Privacy switched on") : T("Privacy switched off"), "good"); pvBadgeRefresh(); render();
  } });
  if (!d.enabled) retention.classList.add("pv-off");
  main.append(pageHead("🛡️ " + I18N.tr(T("Privacy"))),
    h("section.card.pv-master", h("label.switch-wrap", master, h("span.switch-ui")),
      h("div.grow", h("strong", T("Privacy clean-up")), h("div.small.muted", d.enabled
        ? T("On: entries past their retention period are counted, shown in the menu and can be cleaned up.")
        : T("Off: nothing is counted, no clean-up runs and no badge. The retention periods stay saved.")))),
    h("div.pv-hint", h("span", "ℹ️"), h("p.small", T("Older copies can still be in your backups and in the history of Home Assistant. Delete old backups too if the data should be gone everywhere."))),
    // groups on the page background with their folds, like «Family» and «Settings» (the master switch stays on top)
    setGroup("pv.keep", "🗓️", T("Retention")), retention,
    setGroup("pv.clean", "🗑️", T("Clean-up")), cleanup, past, child);
  const tr = k => I18N.tr(k), same = (a, b) => a.unit === b.unit && (a.unit === "forever" || a.n === b.n);
  const changedN = d.kinds.filter(k => !same(k.retention, k.default)).length, due = kindsDue.reduce((a, k) => a + k.count, 0);
  retention.dataset.fold = "retention";
  retention.dataset.status = changedN ? tr(T("{0} changed from the default")).replace("{0}", fmt(changedN)) : tr(T("All defaults"));
  cleanup.dataset.fold = "cleanup";
  cleanup.dataset.status = !d.enabled ? tr(T("Switched off")) : [due ? tr(T("{0} entries ready for a clean-up run")).replace("{0}", fmt(due)) : tr(T("Nothing to clean up")),
    tr(d.auto ? T("Automatic clean-up switched on") : T("Automatic clean-up switched off"))].join(" · ");
  past.dataset.fold = "runs";
  past.dataset.status = d.runs.length ? tr(T("Last run: {0}")).replace("{0}", fmtDateTime(d.runs[0].at)) : tr(T("No clean-up so far."));
  if (child) { child.dataset.fold = "child"; child.dataset.status = kids.map(p => p.name).join(", "); }
  foldBoxes(main, "pv");
}
