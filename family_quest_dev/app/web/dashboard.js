// Family Quest Dashboard – read-only wall display for a kiosk browser (tablet, TV, old phone).
// Opened as dashboard?key=… (the key is set in the parent area → Dashboard). Refreshes itself.
"use strict";
const app = document.getElementById("app");
const KEY = new URLSearchParams(location.search).get("key") || "";
let timer = null, cfgTheme = null, wake = null;

function clock() {
  const now = new Date();
  return h("div.k-clock",
    h("div.k-time", now.toLocaleTimeString(I18N.locale, { hour: "2-digit", minute: "2-digit" })),
    h("div.k-date", now.toLocaleDateString(I18N.locale, { weekday: "long", day: "numeric", month: "long" })));
}

function kidCard(k, w) {
  const l = k.learning;
  const open = (k.chores || []).filter(c => !c.done), done = (k.chores || []).filter(c => c.done);
  return h("section.k-card.k-kid", { style: `--kid:${k.color || "var(--accent)"}` },
    h("div.k-who", h("div.k-av", avatarSvg(k.avatar, 96)),
      h("div.grow", C(k.name, "h2"),
        h("div.k-chips",
          l ? h("span.k-chip", "⭐ Level " + l.level) : null,
          k.streak != null ? h("span.k-chip", "🔥 " + k.streak) : null,
          ...(k.balances || []).map(b => h("span.k-chip", b.icon + " " + fmt(b.value))))),
      k.weather ? h("div.k-weather", { title: k.weather.name ? I18N.tr(k.weather.name) : "" }, k.weather.icon) : null),
    l ? h("div.k-learn", h("div.row", h("span.grow", T("Daily goal")), h("b", fmt(l.xp_today) + " / " + l.goal + " XP")),
      bar(l.xp_today, l.goal, l.xp_today >= l.goal ? "var(--good)" : "var(--kid)")) : null,
    k.chores ? h("div.k-chores",
      h("div.small.muted", "🧹 ", T("Chores today"), " · ", done.length + " / " + k.chores.length),
      !k.chores.length ? h("div.muted", T("No chores today.")) :
        !open.length ? h("div.k-alldone", "✅ ", T("All done!")) :
        h("ul", ...open.slice(0, 6).map(c => h("li", h("span.k-ic", c.icon), C(c.title))),
          open.length > 6 ? h("li.muted", "+ " + (open.length - 6)) : null)) : null);
}

function weatherAlarm(a) {
  if (!a.now && !a.hints.length) return null;
  return h("section.k-card.k-alarm" + (a.hints.length ? ".on" : ""),
    a.now ? h("div.k-wnow", h("span.k-wicon", a.now.icon), a.now.temperature != null ? h("b", Math.round(a.now.temperature) + "°") : null,
      a.now.chance ? h("span.small.muted", "💧 " + a.now.chance + " %") : null) : null,
    h("div.k-hints", ...(a.hints.length ? a.hints.map(x => h("div.k-hint", h("span", x.icon), C(I18N.tr(x.text)))) : [h("div.muted", T("Nothing special – have a nice day!"))])));
}

function familyRow(d) {
  const parts = [];
  if (d.family_goal) {
    const g = d.family_goal;
    parts.push(h("section.k-card", h("h3", "🤝 ", T("Family goal")),
      h("div.row", C(g.title, "strong.grow"), h("b", fmt(g.value) + " / " + fmt(g.target))), bar(g.value, g.target, "var(--good)")));
  }
  if (d.todos) parts.push(h("section.k-card", h("h3", "✅ ", T("Open to-dos")),
    !d.todos.length ? h("div.muted", T("Nothing open.")) :
      h("ul.k-list", ...d.todos.slice(0, 8).map(t => h("li", C(t.title), t.who ? h("span.small.muted", " · ", C(t.who)) : null)))));
  if (d.events) parts.push(h("section.k-card", h("h3", "📅 ", T("Events")),
    !d.events.length ? h("div.muted", T("No events today.")) :
      h("ul.k-list", ...d.events.slice(0, 8).map(e => {
        const s = new Date(e.start), today = new Date().toDateString() === s.toDateString();
        const when = e.all_day ? (today ? I18N.tr(T("Today")) : s.toLocaleDateString(I18N.locale, { weekday: "short" }))
          : (today ? "" : s.toLocaleDateString(I18N.locale, { weekday: "short" }) + " ") + s.toLocaleTimeString(I18N.locale, { hour: "2-digit", minute: "2-digit" });
        return h("li", h("b.k-when", when), " ", C(e.title));
      }))));
  return parts.length ? h("div.k-family", ...parts) : null;
}

function draw(d) {
  if (d.theme !== cfgTheme) { cfgTheme = d.theme; if (d.theme === "auto") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = d.theme; }
  document.title = d.title + " – Dashboard";
  const w = new Set(d.widgets);
  app.replaceChildren(h("div.k-page",
    h("header.k-head", d.crest ? h("span.k-crest", crestSvg(d.crest, { ribbon: false })) : h("img", { src: "img/icon.svg", alt: "", width: 44, height: 44 }), C(d.title, "h1.grow"), w.has("clock") ? clock() : null),
    d.weather_alarm ? weatherAlarm(d.weather_alarm) : null,
    ...(d.special_times || []).map(x => {                 // FamilyTime / OfflineTime of the calendar, with a countdown
      const now = Date.now(), a = new Date(x.start).getTime(), b = new Date(x.end).getTime();
      const left = ms => { const m = Math.max(0, Math.round(ms / 60000)); return (m >= 60 ? Math.floor(m / 60) + " h " : "") + (m % 60) + " min"; };
      return h("section.k-card.k-special." + x.kind + (x.active ? ".now" : ""), h("span.k-sp-ic", x.icon || (x.kind === "offlinetime" ? "📵" : "👨‍👩‍👧")),
        h("div.grow", C(x.title, "strong"), h("div.small", now < a ? I18N.tr(T("starts in {0}")).replace("{0}", left(a - now))
          : I18N.tr(T("still {0} – until {1}")).replace("{0}", left(b - now)).replace("{1}", fmtTime(x.end)))));
    }),
    h("div.k-kids" + (d.kids.length > 2 ? ".many" : ""), ...d.kids.map(k => kidCard(k, w))),
    familyRow(d)));
}

let loading = false;
async function load() {
  clearTimeout(timer);
  if (loading) return;                                    // one refresh at a time – never two loops side by side
  loading = true;
  let refresh = 60;
  try {
    const d = await api("dashboard?key=" + encodeURIComponent(KEY));
    refresh = d.refresh || 60;
    draw(d);
  } catch (e) {
    if (e.status === 403) {
      app.replaceChildren(h("div.k-error", h("h1", "🔒 ", T("Dashboard not available")),
        h("p", T("The link is not valid (any more) or the dashboard is switched off. Copy the link again in the parent area → Dashboard."))));
      refresh = 300;
    } else app.querySelector(".k-head")?.classList.add("k-offline");
  }
  loading = false;
  clearTimeout(timer);
  timer = setTimeout(load, refresh * 1000);
}

// keep a wall tablet awake while the page is visible (where the browser allows it)
async function keepAwake() { try { wake = await navigator.wakeLock.request("screen"); } catch {} }
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") { keepAwake(); load(); } });
setInterval(() => { const c = app.querySelector(".k-clock"); if (c) c.replaceWith(clock()); }, 15000);
I18N.ready.then(() => { keepAwake(); load(); });
