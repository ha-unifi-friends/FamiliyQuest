// ---------------------------------------------------------------- 📅 Family calendar: events, holidays, imports, Home Assistant calendars
// A part of the parent area (parent.js): loaded after it, before boot() runs (eltern.html).
"use strict";

// ---------------------------------------------------------------- family calendar
const isoDay = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const EVENT_ICONS = ["🎂", "🏖️", "🎉", "🏫", "⚽", "🎵", "🩺", "✈️", "🎄", "⭐"];
async function calendarView(main) {
  // views: list · day · week · month · year – anchored at P.calDate
  const VIEWS = [["list", T("List")], ["day", T("Day")], ["week", T("Week")], ["month", T("Month")], ["year", T("Year")]];
  const view = P.calView || (innerWidth <= 760 ? "list" : "month");      // phones start with the list
  const anchor = P.calDate ? new Date(P.calDate + "T12:00") : new Date();       // local noon – not UTC midnight
  anchor.setHours(12, 0, 0, 0);
  const addDays = (x, n) => { const y = new Date(x); y.setDate(y.getDate() + n); return y; };
  const monday = x => addDays(x, -((x.getDay() + 6) % 7));
  let from, to;
  if (view === "day") { from = to = anchor; }
  else if (view === "week") { from = monday(anchor); to = addDays(from, 6); }
  else if (view === "year") { from = new Date(anchor.getFullYear(), 0, 1, 12); to = new Date(anchor.getFullYear(), 11, 31, 12); }
  else {
    const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1, 12), last = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0, 12);
    from = view === "month" ? monday(first) : first; to = view === "month" ? addDays(last, 6 - (last.getDay() + 6) % 7) : last;
  }
  const d = await call(`parent/calendar?start=${isoDay(from)}&end=${isoDay(to)}`);
  const mark = (sec, id, status) => { sec.dataset.fold = id; if (status != null) sec.dataset.status = status; return sec; };
  const evs = d.events;
  const onDay = day => evs.filter(e => e.start.slice(0, 10) <= day && (e.end || e.start).slice(0, 10) >= day);
  const time = e => e.all_day ? "" : fmtTime(e.start) + " ";
  const open = e => e.readonly ? toast("🔒 " + I18N.tr(T("From Home Assistant – read only"))) : eventDialog(e);
  const chip = e => h("button.cal-ev" + (e.readonly ? ".ro" : "") + (e.kind ? "." + e.kind : ""), {
    title: (e.readonly ? "🔒 " + e.calendar + " · " : "") + e.title + (e.game ? " · " + ftGameLine(e.game) : ""), onclick: ev => { ev.stopPropagation(); open(e); } },
    e.icon ? e.icon + " " : "", time(e), C(e.title), e.game ? h("span.cal-game", " · " + e.game.icon + " ", C(ftTitle(e.game))) : null);
  const today = isoDay(new Date());
  const go = (v, date) => { P.calView = v; P.calDate = date ? isoDay(date) : P.calDate; render(); };
  const step = n => {
    const x = new Date(anchor);
    if (view === "day") x.setDate(x.getDate() + n);
    else if (view === "week") x.setDate(x.getDate() + 7 * n);
    else if (view === "year") x.setFullYear(x.getFullYear() + n);
    else x.setMonth(x.getMonth() + n, 1);
    P.calDate = isoDay(x); render();
  };
  const title = view === "day" ? anchor.toLocaleDateString(I18N.locale, { weekday: "long", day: "numeric", month: "long", year: "numeric" })
    : view === "week" ? fmtDate(from, { day: "numeric", month: "short" }) + " – " + fmtDate(to, { day: "numeric", month: "short", year: "numeric" })
    : view === "year" ? String(anchor.getFullYear()) : anchor.toLocaleDateString(I18N.locale, { month: "long", year: "numeric" });
  const fmtRange = e => { const a = new Date(e.start.slice(0, 10) + "T12:00"), b = new Date((e.end || e.start).slice(0, 10) + "T12:00");
    const f = x => x.toLocaleDateString(I18N.locale, { weekday: "short", day: "numeric", month: "short" });
    return f(a) + (b > a ? " – " + f(b) : "") + (e.all_day ? "" : " · " + fmtTime(e.start)); };
  const wd = [...Array(7).keys()].map(i => new Date(2024, 0, 1 + i).toLocaleDateString(I18N.locale, { weekday: "short" }));
  const sorted = list => [...list].sort((a, b) => (a.all_day === b.all_day ? 0 : a.all_day ? -1 : 1) || a.start.localeCompare(b.start));

  let body;
  if (view === "month") {
    const cells = [];
    for (let x = new Date(from); x <= to; x = addDays(x, 1)) {
      const day = isoDay(x), other = x.getMonth() !== anchor.getMonth(), list = sorted(onDay(day));
      cells.push(h("div.cal-day" + (other ? ".other" : "") + (day === today ? ".today" : ""), { onclick: () => eventDialog({ start: day, end: day, all_day: true }) },
        h("button.cal-n", { onclick: ev => { ev.stopPropagation(); go("day", x); } }, String(x.getDate())),
        ...list.slice(0, 4).map(chip), list.length > 4 ? h("span.small.muted", "+" + (list.length - 4)) : null));
    }
    body = h("div.cal-grid", ...wd.map(w => h("div.cal-wd", w)), ...cells);
  } else if (view === "week") {
    const cols = [];
    for (let x = new Date(from); x <= to; x = addDays(x, 1)) {
      const day = isoDay(x), list = sorted(onDay(day));
      cols.push(h("div.cal-wcol" + (day === today ? ".today" : ""), { onclick: () => eventDialog({ start: day, end: day, all_day: true }) },
        h("button.cal-whead", { onclick: ev => { ev.stopPropagation(); go("day", x); } }, h("span.small.muted", wd[(x.getDay() + 6) % 7]), h("b", String(x.getDate()))),
        ...list.map(chip)));
    }
    body = h("div.cal-week", ...cols);
  } else if (view === "day") {
    const list = sorted(onDay(isoDay(anchor)));
    const allDay = list.filter(e => e.all_day), timed = list.filter(e => !e.all_day);
    const hours = [...Array(24).keys()].filter(hh => hh >= 6 || timed.some(e => +e.start.slice(11, 13) === hh));
    body = h("div.cal-dayview",
      allDay.length ? h("div.cal-allday", ...allDay.map(chip)) : null,
      ...hours.map(hh => h("div.cal-hour", { onclick: () => eventDialog({ start: isoDay(anchor) + "T" + String(hh).padStart(2, "0") + ":00",
          end: isoDay(anchor) + "T" + String(Math.min(23, hh + 1)).padStart(2, "0") + ":00", all_day: false }) },
        h("span.cal-hh", fmtTime(new Date(2024, 0, 1, hh))), h("div.grow", ...timed.filter(e => +e.start.slice(11, 13) === hh).map(chip)))));
  } else if (view === "year") {
    body = h("div.cal-year", ...[...Array(12).keys()].map(mi => {
      const f = new Date(anchor.getFullYear(), mi, 1, 12), l = new Date(anchor.getFullYear(), mi + 1, 0, 12);
      const cells = [...Array((f.getDay() + 6) % 7)].map(() => h("span"));
      for (let x = new Date(f); x <= l; x = addDays(x, 1)) {
        const day = isoDay(x), n = onDay(day).length;
        cells.push(h("button.cal-yd" + (n ? ".has" : "") + (day === today ? ".today" : ""), { title: n ? onDay(day).map(e => e.title).join(", ") : "", onclick: () => go("day", x) }, String(x.getDate())));
      }
      return h("div.cal-ymonth", h("button.cal-ytitle", { onclick: () => go("month", f) }, f.toLocaleDateString(I18N.locale, { month: "long" })),
        h("div.cal-ygrid", ...wd.map(w => h("span.cal-ywd", w.slice(0, 2))), ...cells));
    }));
  } else {
    const list = sorted(evs).sort((a, b) => a.start.localeCompare(b.start));
    body = h("ul.cal-list", ...list.map(e => h("li.row", { onclick: () => open(e) },
      h("span.cal-when", fmtRange(e)), h("span.grow", e.icon ? e.icon + " " : "", C(e.title),
        e.game ? [h("br"), h("span.small.ftg-line", e.game.icon + " ", C(ftGameLine(e.game)))] : null), e.readonly ? h("span.small.muted", "🔒 ", C(e.calendar)) : null)),
      !list.length ? h("li.muted", T("No events this month.")) : null);
  }
  main.append(
    pageHead(T("Calendar"),
      h("button.btn.ghost", { onclick: () => eventDialog({ kind: "familytime", start: today + "T18:00", end: today + "T20:00", all_day: false }) }, "+ 👨‍👩‍👧 FamilyTime"),
      h("button.btn.ghost", { onclick: () => eventDialog({ kind: "offlinetime", start: today + "T14:00", end: today + "T17:00", all_day: false, options: { internet: true, games: true } }) }, "+ 📵 OfflineTime"),
      h("button.btn", { onclick: () => eventDialog({ start: today, end: today, all_day: true }) }, "+ ", T("New event"))),
    h("section.card.sec",
      h("div.row.wrap.cal-head",
        h("div.seg.cal-views", ...VIEWS.map(([k, n]) => h("button" + (k === view ? ".on" : ""), { onclick: () => go(k) }, n))),
        h("div.row.grow.cal-nav", h("button.icon-btn", { onclick: () => step(-1), title: T("Back") }, "‹"), h("h2.grow.center", title),
          h("button.btn.small.ghost", { onclick: () => { P.calDate = null; render(); } }, T("Today")), h("button.icon-btn", { onclick: () => step(1), title: T("Next") }, "›"))),
      body),
    // below the calendar: groups on the page background with their folds (like «Family» and «Settings»)
    setGroup("cal.templates", "🏖️", T("Holidays")), mark(await holidaySection(), "holidays"),
    setGroup("cal.sources", "🔗", T("Other calendars")), mark(importSection(d.sources), "import",
      d.sources.length ? I18N.tr(d.sources.length === 1 ? T("1 import") : T("{0} imports")).replace("{0}", d.sources.length) : I18N.tr(T("No imports yet"))),
    mark(haCalendarSection(d.settings), "ha", !P.meta.ha ? I18N.tr(T("Home Assistant is not connected"))
      : (d.settings.ha_calendars || []).length ? I18N.tr(T("{0} shown")).replace("{0}", (d.settings.ha_calendars || []).length) : I18N.tr(T("None shown"))));
  foldBoxes(main, "cal");
}

function eventDialog(e) {
  const isNew = !e.id;
  const title = h("input", { type: "text", maxlength: 120, value: e.title || "", placeholder: I18N.tr(T("e.g. Ski camp")) });
  const allDay = h("input", { type: "checkbox", checked: e.all_day !== false });
  const from = h("input"), to = h("input");
  const setType = () => {
    const t = allDay.checked ? "date" : "datetime-local";
    const conv = v => allDay.checked ? (v || "").slice(0, 10) : ((v || "").length > 10 ? v : (v || "") + "T09:00");
    from.type = t; to.type = t; from.value = conv(from.value || e.start); to.value = conv(to.value || e.end || e.start);
  };
  setType(); allDay.onchange = setType;
  const icon = h("input.weather-icon", { type: "text", maxlength: 8, value: e.icon || "" });
  const note = h("input", { type: "text", maxlength: 500, value: e.note || "", placeholder: I18N.tr(T("Note (optional)")) });
  // the kind: an ordinary event, FamilyTime (highlighted with a countdown) or OfflineTime (internet / games off)
  const KINDS = { event: [T("Event"), ""], familytime: ["FamilyTime", "👨‍👩‍👧"], offlinetime: ["OfflineTime", "📵"] };
  let kind = KINDS[e.kind] ? e.kind : (e.kind || "event");
  const o = Object.assign({ internet: false, games: false, profiles: [] }, e.options || {});
  const offBox = h("div.form.offline-opts");
  let kids = (P.profiles || []).filter(p => p.role === "kid");
  if (!P.profiles) call("parent/profiles").then(l => { P.profiles = l; kids = l.filter(p => p.role === "kid"); drawOff(); }).catch(() => {});
  const drawOff = () => offBox.replaceChildren(...(kind !== "offlinetime" ? [] : [
    h("b", T("During the OfflineTime"), fieldInfo(T("Without a tick it is only a notice in the calendar and on the start page."))),
    h("label.check", h("input", { type: "checkbox", checked: o.internet, onchange: ev => { o.internet = ev.target.checked; } }), "🌐 ", T("Internet off (the internet time cannot be started)")),
    h("label.check", h("input", { type: "checkbox", checked: o.games, onchange: ev => { o.games = ev.target.checked; } }), "🎲 ", T("Games of the app locked (learning stays open)")),
    kids.length ? h("div.row.wrap", h("span.small", T("For:")), ...kids.map(k => h("label.check", h("input", { type: "checkbox", checked: o.profiles.includes(k.id),
      onchange: ev => { o.profiles = ev.target.checked ? [...o.profiles, k.id] : o.profiles.filter(x => x !== k.id); } }), C(k.name))),
      h("span.small.muted", T("(none ticked = all children)"))) : null].filter(Boolean)));
  const kindSel = h("div.pin-kind");
  const drawKind = () => kindSel.replaceChildren(...Object.entries(KINDS).filter(([k]) => k === kind || ["event", "familytime", "offlinetime"].includes(kind))
    .map(([k, [n, ic]]) => h("button.btn.small" + (kind === k ? "" : ".ghost"), { type: "button", onclick: () => {
      if (!icon.value || Object.values(KINDS).some(x => x[1] === icon.value)) icon.value = ic;
      if (!title.value || Object.values(KINDS).some(x => x[0] === title.value)) title.value = k === "event" ? "" : n;
      kind = k; drawKind(); drawOff(); } }, ic ? ic + " " : "", I18N.tr(n))));
  if (isNew && kind !== "event" && !title.value) { title.value = KINDS[kind][0]; icon.value = KINDS[kind][1]; }
  drawKind(); drawOff();
  const m = modal(h("div.form", h("h2", isNew ? T("New event") : T("Edit event")),
    ["event", "familytime", "offlinetime"].includes(kind) ? kindSel : null,
    h("label.field", T("Title"), title),
    h("label.check", allDay, T("All day")),
    h("div.grid2", h("label.field", T("From"), from), h("label.field", T("To"), to)),
    h("label.field", T("Symbol"), h("div.row.wrap", icon, ...EVENT_ICONS.map(ic => h("button.icon-btn", { type: "button", onclick: () => { icon.value = ic; } }, ic)))),
    offBox, note,
    e.game ? h("p.small.ftg-line", e.game.icon + " ", C(ftGameLine(e.game)), " · ", h("button.link.small", { type: "button", onclick: () => { m.close(); P.tab = "community"; location.hash = "community"; render(); } }, T("FamilyTime games ›"))) : null,
    h("div.row", h("button.btn", { onclick: save }, T("Save")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")), h("span.grow"),
      !isNew ? h("button.btn.small.bad", { onclick: async () => { if (!(await confirmDialog(I18N.tr(T("Delete this event?"))))) return; await call(`parent/calendar/${e.id}`, { method: "DELETE" }); m.close(); render(); } }, "🗑 ", T("Delete")) : null)));
  title.focus();
  async function save() {
    const body = { title: title.value, start: from.value, end: to.value || from.value, icon: icon.value, note: note.value, kind,
      color: kind === "familytime" ? "#f59f00" : kind === "offlinetime" ? "#495057" : (e.color || ""), options: kind === "offlinetime" ? o : {} };
    try { await call(isNew ? "parent/calendar" : `parent/calendar/${e.id}`, { method: isNew ? "POST" : "PUT", body }); m.close(); toast(T("Saved"), "good"); render(); }
    catch {}
  }
}

// preview of events to take over: checkboxes, duplicates are marked and not chosen
function eventPreview(events, source, done) {
  const box = h("div.cal-preview");
  const sel = events.map(e => !e.duplicate);
  const btn = h("button.btn");
  const count = () => { const n = sel.filter(Boolean).length; btn.textContent = I18N.tr(T("Take over {0} events")).replace("{0}", n); btn.disabled = !n; };
  box.append(h("ul.list", ...events.map((e, i) => h("li.row" + (e.duplicate ? ".dup" : ""),
    h("input", { type: "checkbox", checked: sel[i], onchange: ev => { sel[i] = ev.target.checked; count(); } }),
    h("span.cal-when", fmtDate(e.start.slice(0, 10)) + (e.end && e.end.slice(0, 10) !== e.start.slice(0, 10) ? " – " + fmtDate(e.end.slice(0, 10)) : "")
      + (e.all_day === false ? " · " + fmtTime(e.start) : "")),
    h("span.grow", e.icon ? e.icon + " " : "", C(e.title)), e.duplicate ? h("span.chip.warn", T("already in the calendar")) : null))),
    h("div.row", btn, h("button.btn.ghost", { onclick: () => box.remove() }, T("Cancel"))));
  btn.onclick = async () => {
    const r = await call("parent/calendar/import", { method: "POST", body: { events: events.filter((e, i) => sel[i]), source } });
    toast(I18N.tr(T("{0} events added")).replace("{0}", r.added) + (r.duplicates ? " · " + I18N.tr(T("{0} duplicates skipped")).replace("{0}", r.duplicates) : ""), "good");
    done ? done() : render();
  };
  count();
  return box;
}

async function holidaySection() {
  let cantons = {}; try { cantons = await call("parent/calendar/cantons"); } catch {}
  let last = "CH-TG"; try { last = localStorage.getItem("fq.canton") || last; } catch {}
  const canton = h("select", { translate: "no" }, ...Object.entries(cantons).map(([k, n]) => h("option", { value: k, selected: k === last }, n)));
  const y = new Date().getFullYear();
  const year = h("select", ...[y, y + 1, y + 2].map(v => h("option", { value: v }, String(v))));
  const school = h("input", { type: "checkbox", checked: true }), pub = h("input", { type: "checkbox", checked: true });
  const out = h("div");
  const lang = ({ de: "DE", fr: "FR", it: "IT" })[(I18N.base || "de").slice(0, 2)] || "EN";
  const sec = section("🏖️ " + I18N.tr(T("Templates: school and public holidays")),
    h("div.grid3", h("label.field", T("Canton"), canton), h("label.field", T("Year"), year)),
    h("div.row.wrap", h("label.check", school, T("School holidays")), h("label.check", pub, T("Public holidays")),
      h("button.btn", { onclick: async () => {
        try { localStorage.setItem("fq.canton", canton.value); } catch {}
        out.replaceChildren(h("p.small.muted", "…"));
        try {
          const list = await call(`parent/calendar/holidays?canton=${canton.value}&year=${year.value}&school=${school.checked}&public=${pub.checked}&lang=${lang}`);
          out.replaceChildren(list.length ? eventPreview(list, `holidays:${canton.value}:${year.value}`) : h("p.muted", T("Nothing found.")));
        } catch { out.replaceChildren(); }
      } }, "👀 ", T("Preview"))), out);
  if (cantons[last]) sec.dataset.status = cantons[last];          // the row of the fold: the canton used last
  return sec;
}

function importSection(sources) {
  const file = h("input", { type: "file", accept: ".csv,.ics,.ical,text/csv,text/calendar" });
  const out = h("div");
  file.addEventListener("change", async () => {
    const f = file.files[0]; if (!f) return;
    try {
      const list = await call("parent/calendar/parse", { method: "POST", body: { name: f.name, text: await f.text() } });
      out.replaceChildren(list.length ? eventPreview(list, "file:" + f.name, () => { file.value = ""; render(); }) : h("p.muted", T("No events found in the file.")));
    } catch { file.value = ""; }
  });
  return section("📥 " + I18N.tr(T("Import a calendar file")),
    fileButton(file, "📤 ", T("Choose file…")), out,
    sources.length ? h("div", h("h3", T("Imports")), h("ul.list", ...sources.map(src => h("li.row",
      h("span.grow", C(src.source.replace(/^holidays:/, "🏖️ ").replace(/^file:/, "📄 ")), h("span.small.muted", " · " + src.n + " · " + fmtDate(src.first.slice(0, 10)) + " – " + fmtDate(src.last.slice(0, 10)))),
      h("button.btn.small.ghost", { onclick: async () => {
        if (!(await confirmDialog(I18N.tr(T("Remove all {0} events of this import?")).replace("{0}", src.n)))) return;
        await call(`parent/calendar/source/${encodeURIComponent(src.source)}`, { method: "DELETE" }); render();
      } }, "🗑 ", T("Remove")))))) : null);
}

function haCalendarSection(settings) {
  const chosen = new Set(settings.ha_calendars || []);
  const list = h("div.row.wrap", h("span.small.muted", "…"));
  if (P.meta.ha) call("parent/ha/entities?domain=calendar").then(cals => list.replaceChildren(...(cals.length ? cals.map(c => h("label.check",
    h("input", { type: "checkbox", checked: chosen.has(c.entity_id), onchange: e => e.target.checked ? chosen.add(c.entity_id) : chosen.delete(c.entity_id) }),
    C(c.name || c.entity_id))) : [h("p.small.muted", T("No calendars found in Home Assistant."))]))).catch(() => list.replaceChildren());
  else list.replaceChildren(h("p.small.muted", T("Home Assistant is not connected")));
  return section("🏠 " + I18N.tr(T("Calendars from Home Assistant")),
    list, h("button.btn.small", { onclick: async () => { await call("parent/calendar/settings", { method: "PUT", body: { ha_calendars: [...chosen] } }); toast(T("Saved"), "good"); render(); } }, "💾 ", T("Save")));
}
