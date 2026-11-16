// Family Quest – the learning app for children (and parents who learn along).
"use strict";

const S = { info: null, me: null, profile: null, lesson: null, idle: null };
const app = $("#app");
// answer tiles: poker suits on four clearly different hues (shared/base.css --ans-1…4)
// weather alarm hints come from the server (weatheralarm.py) – marked here for the dictionaries
const WEATHER_HINTS = [T("Thunderstorm possible – better stay inside when it starts."), T("Rain today – take your rain jacket or umbrella!"),
  T("Snow – warm shoes, gloves and a cap!"), T("Strong wind – hold on to your cap!"), T("Cold today – put on a warm jacket!"),
  T("Hot today – drink a lot, sun cream and a cap!")];
const ANSWER_STYLE = [["ans-1", "♠\uFE0E"], ["ans-2", "♥\uFE0E"], ["ans-3", "♦\uFE0E"], ["ans-4", "♣\uFE0E"]];   // \uFE0E: as text, not as emoji
const PRAISE = [T("Great!"), T("Super!"), T("Well done!"), T("Exactly!"), T("Perfect!")];

// ---------------------------------------------------------------- start & routing
async function boot() {
  try { S.info = await api("info"); } catch (e) { return fatal(e); }
  if (S.info.sound === false && localStorage.getItem("fq.sound") == null) Sound.on = false;
  window.addEventListener("hashchange", route);
  ["pointerdown", "keydown"].forEach(ev => document.addEventListener(ev, idleReset, { passive: true }));
  if ("serviceWorker" in navigator && location.protocol === "https:") navigator.serviceWorker.register("sw.js").catch(() => {});
  route();
}

function fatal(e) {
  app.replaceChildren(h("div.center-screen", h("div.card", h("h2", T("Family Quest cannot be reached")), h("p.muted", e.message),
    h("button.btn", { onclick: () => location.reload() }, T("Try again")))));
}

let routeSeq = 0;
async function route() {
  const seq = ++routeSeq;                                 // quick taps: only the last navigation draws its page
  const hash = location.hash.replace(/^#\/?/, "");
  // «open in the app» from the parent area: #/as/<login>/<view> – log in, then go on to the view
  const as = hash.match(/^as\/([A-Za-z0-9_.\-]+)\/?(.*)$/);
  if (as) { Auth.kid = as[1]; history.replaceState(null, "", "#/" + as[2]); return route(); }
  const [view, arg] = hash.split("/");
  document.body.classList.remove("quiz-open");          // a full-screen game left by the back button of the browser
  if (!Auth.kid) return profilesView();
  try { await loadMe(); } catch (e) {
    if (seq !== routeSeq) return;
    if (e.status === 401) { Auth.kid = ""; return profilesView(); }
    return fatal(e);
  }
  if (seq !== routeSeq) return;
  if (S.me.offline_lock) return offlineLockView(S.me.offline_lock);
  if (view === "pack" && arg) return packView(decodeURIComponent(arg));
  if (view === "shop") return shopView();
  if (view === "avatar") return avatarView();
  if (view === "family") return familyView();
  if (view === "games") return gamesView();
  if (view === "quiz") return quizView();
  if (view === "quizzes") return quizzesView();
  if (view === "courses") return coursesView();
  if (view === "bingo") return bingoView();
  if (view === "poker") return pokerView();
  if (view === "song") return songView();
  if (view === "tschau" || view === "karussell") return cardsView(view);
  if (view === "domino") return dominoView();
  if (view === "arcade") return arcadeView(arg);
  if (view === "deck") return arg ? deckView(+arg) : decksView();
  return dashboardView();
}

const go = path => { if (location.hash === "#/" + path) route(); else location.hash = "#/" + path; };

async function loadMe() {
  S.me = await api("me");
  S.profile = S.me.profile;
  idleReset();
}

function logout() {
  Auth.kid = ""; Auth.parent = "";
  S.me = S.profile = null;
  location.hash = "#/";
  profilesView();
}

// FamilyTime and OfflineTime from the family calendar: a banner with a countdown
function untilText(ms) {
  const min = Math.max(0, Math.round(ms / 60000)), hh = Math.floor(min / 60), mm = min % 60;
  return (hh ? hh + " h " : "") + mm + " min";
}
function specialBanners(list) {
  return (list || []).map(x => {
    const txt = h("span.small");
    const tick = () => {
      if (!txt.isConnected && txt.dataset.started) return clearInterval(timer);
      txt.dataset.started = "1";
      const now = Date.now(), a = new Date(x.start).getTime(), b = new Date(x.end).getTime();
      txt.textContent = now < a ? I18N.tr(T("starts in {0}")).replace("{0}", untilText(a - now))
        : now < b ? I18N.tr(T("still {0} – until {1}")).replace("{0}", untilText(b - now)).replace("{1}", fmtTime(x.end)) : I18N.tr(T("over"));
    };
    const timer = setInterval(tick, 30000); tick();
    const off = x.kind === "offlinetime";
    const what = off ? [x.options.internet ? T("no internet") : null, x.options.games ? T("no games in the app") : null].filter(Boolean).map(t => I18N.tr(t)).join(" · ") : "";
    return h("section.card.banner.special-banner." + x.kind + (x.active ? ".now" : ""),
      h("span.big-ic", x.icon || (off ? "📵" : "👨‍👩‍👧")),
      h("span.grow", h("strong", C(x.title)), h("br"), txt, what ? [h("br"), h("span.small.muted", what)] : null));
  });
}

// which games this child may play (parent area › Settings › Games – per game and person)
const canPlay = game => !!(S.me && (S.me.games_list || []).includes(game));

// invitations to a duel (Tic-Tac-Toe on two devices) pop up wherever the child is in the app
let duelSeen = 0;
setInterval(async () => {
  if (!Auth.kid || !S.me || !canPlay("ttt") || S.lesson || document.hidden || /arcade\/ttt/.test(location.hash)) return;
  let d; try { d = await api("community/duel"); } catch { return; }
  if (!d || d.status !== "invite" || d.host || d.id === duelSeen) return;
  duelSeen = d.id;
  try { Sound.play("tap"); } catch {}
  const other = d.names.X;
  const m = modal(h("div.form.center", h("h2", "⭕ ", T("Tic-Tac-Toe")), h("p", I18N.tr(T("{0} invites you to Tic-Tac-Toe")).replace("{0}", other)),
    h("div.row.center", h("button.btn.big", { onclick: async () => { m.close(); try { await api("community/duel/accept", { method: "POST" }); } catch {} go("arcade/ttt"); } }, "▶ ", T("Play")),
      h("button.btn.ghost", { onclick: async () => { m.close(); try { await api("community/duel/decline", { method: "POST" }); } catch {} } }, T("No thanks")))));
}, 5000);

function idleReset() {
  clearTimeout(S.idle);
  const min = S.profile && S.profile.auto_logout_min;
  if (min > 0 && Auth.kid) S.idle = setTimeout(() => { if (!S.lesson) { toast(T("Logged out after a break")); logout(); } }, min * 60000);
}

// ---------------------------------------------------------------- shared chrome
// Header like the Family Planer: ☰ menu, me + streak, clock with the season design (animated scene), the actions of
// the current module on the right. No bottom bar – the content runs to the bottom.

function seasonOn() { try { return localStorage.getItem("fq.season") !== "0"; } catch { return true; } }

let _seasonCss = false;
function seasonScene() {
  const se = S.info && S.info.season;
  if (!se || !seasonOn() || !window.FPSEASON) return null;
  if (!_seasonCss) { _seasonCss = true; document.head.append(h("style", FPSEASON.CSS)); }
  const now = new Date();
  const el = h("div.scn");
  try {
    el.innerHTML = FPSEASON.scene({ season: { vis: se.vis, jz: se.jz, key: se.id, wild: 1 }, wx: null, hour: now.getHours(),
      lang: I18N.base === "de" ? "de" : "en", narrow: innerWidth < 700, intensity: "normal" }) + '<div class="shade"></div>';
  } catch (e) { return null; }
  return el;
}

function seasonLabel() {
  const se = S.info && S.info.season;
  return se ? h("span.slab", se.icon, " ", se.builtin ? T(se.name) : C(se.name)) : null;
}

function headClock() {
  const t = h("b"), d = h("span.dt");
  const tick = () => {
    if (!t.isConnected && t._started) return clearInterval(t._iv);
    t._started = true;
    const n = new Date();
    t.textContent = fmtTime(n);
    d.textContent = n.toLocaleDateString(I18N.locale, { weekday: "long", day: "numeric", month: "long" });
  };
  tick(); t._iv = setInterval(tick, 15000);
  return h("span.clk", h("span.tl", t, seasonLabel()), d);
}

function topBar(active, opts = {}) {
  const me = S.me;
  const se = S.info && S.info.season;
  const head = h("header.top.fq-head" + (se && seasonOn() ? ".sc" : ""), { style: se && se.accent ? { "--season": se.accent } : null },
    seasonScene(),
    h("div.head-row",
      h("button.icon-btn.menu-btn", { title: T("Menu"), "aria-label": T("Menu"), onclick: () => openDrawer(active) }, "☰"),
      opts.back ? h("button.icon-btn.back-btn", { title: T("Back"), "aria-label": T("Back"), onclick: opts.back }, "←") : null,
      h("button.me", { onclick: () => go("avatar"), title: T("Me") },
        avatarSvg(me.profile.avatar, 44),
        h("span.me-text", C(me.profile.name, "strong"), h("span.level-chip", "Level " + me.level.level))),
      h("span.streak", { title: T("Days in a row with the daily goal") }, "🔥 ", h("b", String(me.streak))),
      headClock(),
      h("span.grow"),
      opts.actions ? h("div.head-actions", ...[].concat(opts.actions)) : null));
  return head;
}

function openDrawer(active) {
  openAppMenu({ active, season: S.info.season, seasonOn: seasonOn(),
    onGo: key => { if (key === "planer") location.href = "planer"; else go(key === "home" ? "" : key); },
    onSeason: () => { try { localStorage.setItem("fq.season", seasonOn() ? "0" : "1"); } catch {} route(); },
    onLogout: logout });
}

/** screen(active, [{back, actions}], ...content) – the optional options object sets the header of this module. */
function screen(active, ...content) {
  const opts = content[0] && content[0].constructor === Object ? content.shift() : {};
  app.replaceChildren(h("div.screen", topBar(active, opts), h("main.content", ...content)));
  window.scrollTo(0, 0);
}

// ---------------------------------------------------------------- profiles
async function profilesView() {
  let profiles = [];
  try { profiles = await api("profiles"); } catch (e) { return fatal(e); }
  const kids = profiles.filter(p => p.role === "kid"), parents = profiles.filter(p => p.role === "parent");
  const tile = p => h("button.profile-tile", { onclick: () => login(p) }, avatarSvg(p.avatar, 120),
    C(p.name, "strong"), p.has_pin ? h("span.lock", { title: T("With PIN") }, "🔒") : null);
  const body = h("div.profiles-screen",
    h("div.row.profiles-head", h("h1.grow", T("Log in")), themeBtn(), langPicker()),
    S.info.setup_needed
      ? h("div.card.welcome", h("h2", T("Welcome to Family Quest!")), h("p", T("A parent sets up the profiles first.")),
          h("a.btn.big", { href: "eltern" }, T("Set up now")))
      : null,
    kids.length ? h("div.profile-grid", ...kids.map(tile)) : (!S.info.setup_needed ? h("p.muted.center", T("No child profile yet – add one in the parent area.")) : null),
    parents.length ? h("div.parents-row", h("span.muted", T("Learn along:")), ...parents.map(p =>
      h("button.parent-chip", { onclick: () => login(p) }, avatarSvg(p.avatar, 36), C(p.name)))) : null,
    S.info.parent_ha_only && !S.info.via_ha ? null : h("a.parent-link", { href: "eltern" }, "🔐 ", T("Parent area")));
  app.replaceChildren(body);
}

function login(p) {
  const done = res => {
    Auth.kid = res.token;
    if (res.parent_token) Auth.parent = res.parent_token;
    Sound.play("tap");
    location.hash = "#/";
    route();
  };
  if (!p.has_pin) return api("login", { method: "POST", body: { profile_id: p.id } }).then(done).catch(e => toast(e.message, "bad"));
  if (p.pin_kind === "symbols" && p.symbol_set) {
    // picture PIN: the 24 symbols come in a new order every time, so a watched pattern does not help
    const m = modal(h("div", h("div.center", avatarSvg(p.avatar, 80)),
      symbolPad({ title: C(p.name), symbols: p.symbol_set, onSubmit: async ids => {
        const res = await api("login", { method: "POST", body: { profile_id: p.id, pin: "sym:" + ids.join(",") } });
        m.close(); done(res);
      } })));
    return;
  }
  const m = modal(h("div", h("div.center", avatarSvg(p.avatar, 90)),
    pinPad({ title: C(p.name), length: 4, maxLength: p.role === "kid" ? 4 : 8, onSubmit: async pin => {
      const res = await api("login", { method: "POST", body: { profile_id: p.id, pin } });
      m.close(); done(res);
    } })));
}

// ---------------------------------------------------------------- dashboard
function dashboardView() {
  const me = S.me;
  const goal = me.daily_goal, xp = me.xp_today;
  const met = xp >= goal;
  const today = h("section.card.today",
    ring(xp, goal, { size: 132, stroke: 14, color: met ? "var(--good)" : "var(--accent)",
      label: h("span", h("b.big", fmt(xp)), h("br"), h("span.small.muted", "/ " + fmt(goal) + " XP")) }),
    h("div.today-text",
      h("h2", met ? T("Daily goal reached! 🎉") : T("Today's goal")),
      h("p.muted", met ? T("Everything extra counts for your level.") : T("A short lesson mixes repetitions and new words.")),
      h("button.btn.big", { onclick: () => startLesson({ mode: "daily" }) }, "▶ ", T("Daily lesson"))));

  const subjects = h("section",
    h("div.row", h("h2.grow", T("Subjects")), h("button.btn.small.ghost", { onclick: () => go("courses") }, "🌍 ", T("Language courses & more"))),
    me.subjects.length
      ? h("div.subject-grid", ...me.subjects.map(s => h("button.subject", { style: { "--c": s.color }, onclick: () => go("pack/" + encodeURIComponent(s.pack)) },
          h("span.subject-ic", s.icon),
          h("span.subject-body",
            C(s.title, "strong"),
            h("span.row.small", stars(Math.round(5 * s.stars / Math.max(1, s.max_stars))), h("span.muted", s.percent + " %")),
            s.next ? h("span.small.next", T("Next:"), " ", C(s.next.title)) : h("span.small.next", "🏆 ", T("All done!")),
            s.due ? h("span.due", s.due + " " + T("to repeat")) : null))))
      : h("p.muted", T("No subjects active yet – a parent can switch on packs.")));

  const sections = [...(me.profile.crown ? [h("section.card.banner.crown-banner", h("span.big-ic", "👑"), h("strong", T("Today you wear the crown!")))] : []),
    ...(me.weather ? [h("section.card.banner.weather-banner", h("span.weather-big", me.weather.icon),
      h("div", h("div.small.muted", T("Your weather today")), me.weather.name ? h("strong", I18N.tr(me.weather.name)) : null))] : []),
    ...(me.weather_alarm && me.weather_alarm.hints.length ? [h("section.card.banner.alarm-banner",
      h("span.big-ic", me.weather_alarm.now ? me.weather_alarm.now.icon : "🌂"),
      h("div.grow", ...me.weather_alarm.hints.map(x => h("div", x.icon, " ", C(I18N.tr(x.text), "strong")))))] : []),
    ...specialBanners(me.special_times), ...communityBanners(me.community), today];
  if (me.profile && me.has_devices) sections.push(devicesCard());
  if (me.chores) sections.push(choresCard(me.chores));
  sections.push(subjects, deckHomeCard(), pointsCard());
  if (me.goals.length) sections.push(h("section.card", h("h2", "🎯 ", T("Goals")), ...me.goals.map(g =>
    h("div.goal", h("div.row", C(g.title, "span.grow"), h("b", g.percent ? g.value + " %" : g.value + " / " + g.target + " ★"), g.done ? "✅" : null),
      bar(g.value, g.target, g.color)))));
  if (me.family_goal) sections.push(familyGoalCard(me.family_goal));
  if (me.badges.length) sections.push(badgesCard(me.badges));
  screen("home", ...sections);
}

/** Block time «only a message»: the app shows that it is OfflineTime until it ends. */
function offlineLockView(lock) {
  const until = new Date(lock.until);
  const left = h("b.offline-left");
  const tick = () => {
    if (!left.isConnected && t) return clearInterval(t);
    const ms = until - Date.now();
    // over: ask the server again – but at most every 15 s (a device clock running ahead must not cause a request loop)
    if (ms <= 0) { clearInterval(t); left.textContent = "…"; return setTimeout(() => { if (left.isConnected) route(); }, ms > -1000 ? 1500 : 15000); }
    left.textContent = untilText(ms);
  };
  app.replaceChildren(h("div.offline-lock",
    h("div.offline-ic", "📵"), h("h1", T("OfflineTime")),
    h("p", T("Time for something without a screen – Family Quest is back at {0}.").replace("{0}", fmtTime(until))),
    h("p.small.muted", "⏳ ", left),
    h("button.btn.ghost", { onclick: logout }, "🔒 ", T("Log out"))));
  let t = null;
  tick(); t = setInterval(tick, 1000);
}

let netTimer = null;
function internetCard(st) {
  clearInterval(netTimer);
  const clock = h("b.net-clock");
  const fmtClock = s => Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
  let left = st.seconds_left || 0;
  const draw = () => { clock.textContent = st.running ? fmtClock(Math.max(0, left)) : fmt(st.minutes) + " min"; };
  draw();
  if (st.running) {
    netTimer = setInterval(() => {
      if (!clock.isConnected) return clearInterval(netTimer);
      left--; draw();
      if (left <= 0) { clearInterval(netTimer); route(); return; }
      // every 30 s: only the clock is corrected from the server – the page stays where it is (no jump to the top)
      if (left % 30 === 0) api("me/internet").then(s => { if (s && s.running) left = s.seconds_left || left; else route(); }).catch(() => {});
    }, 1000);
  }
  const act = async path => {
    try { await api("me/internet/" + path, { method: "POST" }); Sound.play(path === "start" ? "right" : "tap"); route(); }
    catch (e) { toast(e.message, "bad"); }
  };
  return h("div.net.net-inline" + (st.running ? ".on" : ""),
    h("div.net-ic", st.running ? "🟢" : "🌐"),
    h("div.grow", h("h2", T("Internet time")), clock,
      h("div.small.muted", st.block ? T("Block time – the internet is off until {0}.").replace("{0}", fmtTime(st.block.until))
        : st.running ? T("Internet is on – the time runs.") : st.minutes >= 1 ? T("Start when you want to go online.") : T("No minutes left – earn some in the shop.")),
      st.budget ? h("div.small.muted", "📅 ", I18N.tr(T("Budget: {0} of {1} min left")).replace("{0}", fmt(st.budget.left)).replace("{1}", fmt(st.budget.total)),
        st.extra ? " · ➕ " + fmt(st.extra) + " min" : "", " · ", I18N.tr(T("new from {0}")).replace("{0}", fmtDate(st.budget.reset_at, { weekday: "short" }) + " " + fmtTime(st.budget.reset_at))) : null),
    st.running ? h("button.btn.big.bad", { onclick: () => act("stop") }, "⏸ ", T("Pause"))
      : h("button.btn.big.good", { disabled: !st.can_start, onclick: () => act("start") }, "▶ ", T("Start")));
}

function badgesCard(badges) {
  const got = badges.filter(b => b.earned).length;
  return h("section.card", h("div.row", h("h2.grow", "🏅 ", T("Badges")), h("span.muted", got + " / " + badges.length)),
    h("p.small.muted", T("Tap a badge to see how you get it.")),
    h("div.badges", ...badges.map(b => h("button.badge" + (b.earned ? ".got" : ".locked"), { onclick: () => badgeInfo(b), "aria-label": b.name },
      h("span.badge-ic", b.icon), b.earned ? null : h("span.badge-lock", "🔒"),
      h("span.small.badge-name", b.name),
      b.earned ? h("span.badge-check", "✓") : h("span.badge-how", b.how),
      !b.earned && b.target > 1 ? bar(b.value, b.target) : null))));
}

function badgeInfo(b) {
  const m = modal(h("div.badge-modal",
    h("div.badge-big" + (b.earned ? "" : ".locked"), b.icon),
    h("h2", b.name),
    b.earned ? h("p.good-text", "✓ ", T("You have this badge!")) : h("p.badge-how-big", b.how),
    !b.earned && b.target > 1 ? h("div.badge-progress", bar(b.value, b.target), h("span.small", fmt(b.value) + " / " + fmt(b.target))) : null,
    b.unlocks.length ? h("p", "🎁 ", T("Unlocks for your avatar:"), " ", b.unlocks.map(n => I18N.tr(n)).join(", ")) : null,
    h("p.small.muted", T("Every new badge also gives XP.")),
    h("button.btn", { onclick: () => m.close() }, T("OK"))));
}

function choresCard(chores) {
  const open = chores.filter(c => !c.done);
  const accIcon = k => ((S.me.accounts || []).find(a => a.key === k) || {}).icon || "🪙";
  return h("section.card.chores", h("h2", "🧹 ", T("Today's chores")),
    chores.length ? h("ul.chore-list", ...chores.map(c => h("li" + (c.done ? ".done" : c.pending ? ".pending" : ""),
      h("button.chore-check", { disabled: c.done || c.pending, "aria-label": T("Done"), onclick: async ev => {
        const btn = ev.currentTarget; btn.disabled = true;
        try {
          const r = await api(`me/chores/${encodeURIComponent(c.uid)}/done`, { method: "POST" });
          Sound.play("right");
          toast(r.status === "pending" ? T("Sent to your parents for checking") : T("Well done!"), "good");
          route();
        } catch (e) { toast(e.message, "bad"); btn.disabled = false; }
      } }, c.done ? "✓" : c.pending ? "⏳" : ""),
      c.icon ? h("span.chore-ic", c.icon) : null,
      h("span.grow", C(c.summary),
        c.pending ? h("span.chore-note", T("waiting for confirmation")) : null,
        c.redo && !c.done && !c.pending ? h("span.chore-note.redo", T("Please do it once more")) : null,
        c.weekly ? h("span.chore-note", T("this week")) : null),
      c.points ? h("span.chore-pts", accIcon(c.account) + " " + fmt(c.points)) : null))) : h("p.muted", T("No chores today.")),
    open.length === 0 && chores.length ? h("p.good-text", T("All chores done – thank you!")) : null);
}

function pointsCard() {
  const me = S.me;
  const accs = me.accounts.filter(a => a.spendable);
  const nr = me.next_reward;
  return h("section.card.points", h("h2", "🪙 ", T("Points and goodies")),
    h("div.balances", ...accs.map(a => h("div.balance", h("span.bal-ic", a.icon || "🪙"), h("b", fmt(me.balances[a.key], 1)), h("span.small.muted", a.name)))),
    me.internet ? internetCard(me.internet) : null,      // start / pause the internet time right next to the minutes
    nr ? h("div.next-reward", h("div.row", h("span.big-ic", nr.icon), h("span.grow", T("Still {0} until {1}").replace("{0}", fmt(nr.missing)).replace("{1}", nr.name))),
      bar(nr.cost - nr.missing, nr.cost)) : null,
    me.pending.length ? h("p.small.muted", "⏳ ", T("Waiting for approval:"), " ", me.pending.map(p => p.name).join(", ")) : null,
    h("button.btn.ghost", { onclick: () => go("shop") }, "🛍️ ", T("To the shop")));
}

function familyGoalCard(g) {
  return h("section.card.family-goal", h("h2", "🤝 ", T("Family goal")),
    h("div.row", C(g.title, "strong.grow"), h("b", fmt(g.value) + " / " + fmt(g.target))), bar(g.value, g.target, "var(--good)"),
    g.done ? h("p.good-text", T("Reached together! 🎉")) : h("p.small.muted", T("Everyone collects together.")));
}

// ---------------------------------------------------------------- pack / learning path
async function packView(packId) {
  let d;
  try { d = await api("me/packs/" + encodeURIComponent(packId)); } catch (e) { toast(e.message, "bad"); return go(""); }
  const p = d.pack, prog = d.progress;
  const learned = prog.units.some(u => u.seen > 0);
  const BOX = [T("New"), "1", "2", "3", "4", "5"];
  const maxBox = Math.max(1, ...prog.boxes);
  const dueCards = prog.units.filter(u => u.kind === "cards").reduce((a, u) => a + u.due, 0);
  const cardBox = prog.boxes.some(Boolean) ? h("section.card.cardbox",
    h("div.row", h("h2.grow", "🗃️ ", T("Card box")),
      h("button.btn", { onclick: () => startLesson({ mode: "cards", pack: p.id }) }, "🃏 ",
        dueCards ? T("Repeat {0} due cards").replace("{0}", dueCards) : T("Flash cards"))),
    h("div.boxes", ...prog.boxes.map((n, i) => h("div.box" + (i ? ".b" + i : ".new"), { title: i ? T("Box {0}").replace("{0}", i) : T("Not learnt yet") },
      h("b", String(n)), h("div.box-fill", h("i", { style: { height: (100 * n / maxBox) + "%" } })), h("span.small", BOX[i])))),
    h("p.small.muted", T("Every card moves one box up when you know it and back to box 1 when you don't. Box 1 comes daily, box 5 every 16 days."))) : null;
  const path = h("div.path", ...prog.units.map((u, i) => {
    const st = h("button.station" + (u.unlocked ? "" : ".locked") + (u.stars >= 5 ? ".gold" : ""),
      { style: { "--c": p.color }, disabled: !u.unlocked, onclick: () => startLesson({ mode: "path", pack: p.id, unit: u.id }),
        "aria-label": u.title },
      h("span.station-ic", u.unlocked ? (u.icon || String(i + 1)) : "🔒"));
    return h("div.station-wrap" + (i % 2 ? ".right" : ".left"), st,
      h("div.station-label", C(u.title, "strong"), stars(u.stars),
        u.due ? h("span.due", u.due + " " + T("to repeat")) : null,
        u.kind === "generator" ? h("span.small.muted", T("Endless tasks")) : h("span.small.muted", u.seen + " / " + u.count),
        u.kind === "cards" && u.unlocked && u.exercises.includes("karteikarte") ? h("button.btn.small.ghost.cards-btn",
          { onclick: () => startLesson({ mode: "cards", pack: p.id, unit: u.id }), title: T("Flash cards") }, "🃏 ", T("Flash cards")) : null,
        u.kind === "cards" && u.unlocked ? h("button.btn.small.ghost.cards-btn", { title: T("All cards of this unit to my card box"),
          onclick: e => addToDeck({ pack: p.id, unit: u.id }, e.currentTarget) }, "📇") : null));
  }));
  screen("home", { back: () => go("") },
    h("section.pack-head", { style: { "--c": p.color } },
      h("span.pack-ic", p.icon), h("div", C(p.title, "h1"), h("span.small", prog.percent + " % · " + prog.stars + " / " + prog.max_stars + " ★"))),
    h("div.row.pack-actions",
      h("button.btn", { onclick: () => startLesson({ mode: "path", pack: p.id, unit: prog.next || undefined }), disabled: !prog.next }, "▶ ", T("Continue")),
      h("button.btn.ghost", { onclick: () => startLesson({ mode: "quiz", pack: p.id }), disabled: !learned }, "⚡ ", T("Quiz round")),
      p.units.some(u => u.kind === "cards") ? h("button.btn.ghost", { onclick: () => startLesson({ mode: "cards", pack: p.id }) }, "🃏 ", T("Flash cards")) : null),
    cardBox, path);
}

// ---------------------------------------------------------------- lesson player
async function startLesson(opts) {
  let s;
  try { s = await api("me/session", { method: "POST", body: opts }); }
  catch (e) { return toast(e.message, "bad"); }
  S.lesson = { s, i: 0, right: 0, back: location.hash };
  renderStep();
}

function lessonChrome(body, step) {
  const L = S.lesson;
  const total = L.s.steps.length;
  return h("div.lesson",
    h("div.lesson-top",
      h("button.icon-btn", { "aria-label": T("Stop"), title: T("Stop"), onclick: quitLesson }, "✕"),
      h("div.bar.grow.lesson-progress", h("i", { style: { width: (100 * L.i / total) + "%" } })),
      h("span.small.muted", (L.i + 1) + " / " + total)),
    step.timer ? h("div.timer", h("i", { style: { animationDuration: step.timer + "s" } })) : null,
    h("div.lesson-body", body),
    h("div.feedback#feedback", { hidden: true }));
}

function quitLesson() {
  const L = S.lesson;
  if (L && L.i > 0 && L.i < L.s.steps.length && !confirm(I18N.tr(T("Stop the lesson? What you answered so far counts.")))) return;
  if (L && L.i > 0) return finishLesson();
  S.lesson = null;
  location.hash = L ? L.back : "#/";
  route();
}

function renderStep() {
  const L = S.lesson;
  if (L.i >= L.s.steps.length) return finishLesson();
  const step = L.s.steps[L.i];
  const t0 = performance.now();
  let answered = false;
  const submit = async answer => {
    if (answered) return null;
    answered = true;
    clearTimeout(L.timer);
    let res;
    try { res = await api(`me/session/${L.s.id}/answer`, { method: "POST", body: { step: L.i, answer, ms: Math.round(performance.now() - t0) } }); }
    catch (e) { answered = false; toast(e.message, "bad"); return null; }
    if (res.correct) L.right++;
    showFeedback(res, step);
    return res;
  };
  const r = RENDER[step.kind] || RENDER.auswahl;
  app.replaceChildren(lessonChrome(r(step, submit), step));
  if (step.timer) L.timer = setTimeout(() => submit(""), step.timer * 1000);
}

function solutionText(step, res) {
  const s = res.solution;
  if (s == null || typeof s === "object" && !Array.isArray(s)) return "";
  if (step.kind === "rechnen") {
    if (step.input === "fraction") return s[0] + "/" + s[1];
    if (step.input === "div_rest") return s[0] + " R " + s[1];
    return typeof s === "number" ? fmt(s, 6) : String(s);
  }
  return String(s);
}

function showFeedback(res, step) {
  const fb = $("#feedback");
  const good = res.correct;
  Sound.play(good ? "right" : "wrong");
  const sol = good ? "" : solutionText(step, res);
  fb.className = "feedback " + (good ? "good" : "bad");
  fb.replaceChildren(
    h("div.fb-text",
      h("strong.fb-title", good ? PRAISE[Math.floor(Math.random() * PRAISE.length)] : (res.score ? T("Almost!") : T("Not quite"))),
      res.score ? h("div", res.score[0] + " / " + res.score[1] + " " + T("correct")) : null,
      sol ? h("div", T("Correct answer:"), " ", C(sol, "b")) : null,
      res.note ? h("div.small", res.note) : null,
      res.xp ? h("div.small", "+" + fmt(res.xp) + " XP") : null,
      step.kind !== "rechnen" ? h("button.btn.small.ghost.to-deck", { onclick: e => addToDeck({ session: S.lesson.s.id, step: S.lesson.i }, e.currentTarget) },
        "📇 ", T("To my card box")) : null),
    h("button.btn.big" + (good ? ".good" : ".bad"), { onclick: next, id: "next-btn" }, T("Continue")));
  fb.hidden = false;
  setTimeout(() => { const b = $("#next-btn"); b && b.focus(); }, 50);
  function next() { S.lesson.i++; renderStep(); }
}

async function finishLesson() {
  const L = S.lesson;
  let res;
  try { res = await api(`me/session/${L.s.id}/finish`, { method: "POST" }); } catch (e) { toast(e.message, "bad"); }
  S.lesson = null;
  if (!res) { location.hash = L.back; return route(); }
  resultView(res, L.back);
}

function resultView(res, back) {
  const perfect = res.total && res.right === res.total;
  if (res.completed) { Sound.play("done"); confetti(); }
  const gained = Object.entries(res.gained || {}).filter(([, v]) => v > 0);
  const accounts = (S.me && S.me.accounts) || [];
  const accName = k => k === "xp" ? "XP" : ((accounts.find(a => a.key === k) || {}).name || k);
  const accIcon = k => k === "xp" ? "⭐" : ((accounts.find(a => a.key === k) || {}).icon || "🪙");
  app.replaceChildren(h("div.result",
    h("div.result-hero", perfect ? "🏆" : res.right >= res.total / 2 ? "🎉" : "💪"),
    h("h1", perfect ? T("Perfect!") : res.completed ? T("Lesson done!") : T("Good effort!")),
    h("p.big", res.right + " / " + res.total + " " + T("correct")),
    h("div.chips", ...gained.map(([k, v]) => h("span.chip", accIcon(k) + " +" + fmt(v, 1) + " ", accName(k)))),
    res.goal_met ? h("p.good-text", "🎯 ", T("Daily goal reached!")) : null,
    res.streak ? h("p", "🔥 ", T("Streak: {0} days").replace("{0}", res.streak)) : null,
    ...(res.units || []).map(u => h("div.unit-result", C(u.title, "span.grow"), stars(u.stars),
      u.before != null && u.stars > u.before ? h("span.chip.good", "+" + (u.stars - u.before) + " ★") : null)),
    res.badges && res.badges.length ? h("div.card.new-badges", h("h2", T("New badge!")),
      ...res.badges.map(b => h("div.row", h("span.badge-ic", b.icon), h("div", h("strong", b.name), h("div.small.muted", b.description))))) : null,
    h("div.row.center", h("button.btn.big", { onclick: () => { location.hash = back || "#/"; route(); } }, T("Continue")),
      h("button.btn.big.ghost", { onclick: () => go("") }, "🏠"))));
}

// ---------------------------------------------------------------- exercise renderers
const LANG_INFO = { en: ["🇬🇧", T("English")], fr: ["🇫🇷", T("French")], de: ["🇩🇪", T("German")], it: ["🇮🇹", T("Italian")],
  es: ["🇪🇸", T("Spanish")], rm: ["🇨🇭", T("Romansh")], la: ["🏛️", T("Latin")] };
// «🇬🇧 in English» – which language the answer has to be in
function langChip(code) {
  const l = LANG_INFO[code];
  if (!l) return null;
  return h("span.lang-chip", l[0] + " ", T("in {0}").replace("{0}", l[1]));
}

function media(step) {
  if (step.image) return h("img.prompt-img", { src: step.image, alt: "" });
  if (step.emoji) return h("div.prompt-emoji", { translate: "no" }, step.emoji);
  return null;
}
const isEmojiOnly = s => /^[\p{Extended_Pictographic}\p{Regional_Indicator}‍️\s]+$/u.test(s || "");

function promptBlock(step) {
  return h("div.prompt",
    h("p.instruction", step.instruction),
    langChip(step.answer_lang),
    media(step),
    step.prompt ? h("div" + (isEmojiOnly(step.prompt) ? ".prompt-emoji" : ".prompt-text"), { translate: "no" }, step.prompt) : null,
    step.hint ? h("p.small.muted", "💡 ", C(step.hint)) : null);
}

function choiceTiles(options, onPick, render = o => C(o)) {
  return h("div.tiles" + (options.length <= 2 ? ".two" : ""), ...options.map((o, i) => {
    const [cls, shape] = ANSWER_STYLE[i % 4];
    return h("button.tile." + cls, { "data-value": o, onclick: ev => onPick(o, ev.currentTarget) }, h("span.shape", shape), render(o));
  }));
}

function markChoice(container, picked, res) {
  const sol = typeof res.solution === "string" ? res.solution : String(res.solution);
  const norm = s => String(s).trim().toLowerCase();
  container.querySelectorAll(".tile").forEach(b => {
    b.disabled = true;
    if (norm(b.dataset.value) === norm(sol)) b.classList.add("right");
    else if (b === picked) b.classList.add("wrong");
    else b.classList.add("dim");
  });
}

const RENDER = {
  auswahl(step, submit) {
    let tiles;
    tiles = choiceTiles(step.options, async (o, el) => { tiles.querySelectorAll(".tile").forEach(b => b.disabled = true); const r = await submit(o); if (r) markChoice(tiles, el, r); });
    return h("div", promptBlock(step), tiles);
  },

  hoeren(step, submit) {
    const say = () => { if (!speak(step.say, step.lang)) toast(T("This device cannot speak")); };
    setTimeout(say, 300);
    let tiles;
    tiles = choiceTiles(step.options, async (o, el) => { tiles.querySelectorAll(".tile").forEach(b => b.disabled = true); const r = await submit(o); if (r) markChoice(tiles, el, r); });
    return h("div", h("div.prompt", h("p.instruction", step.instruction), langChip(step.answer_lang),
      h("button.speaker", { onclick: say, "aria-label": T("Listen again") }, "🔊")), tiles);
  },

  lueckentext(step, submit) {
    const parts = step.sentence.split(/_{2,}/);
    const gap = h("span.gap", "   ");
    const sentence = h("div.sentence", { translate: "no" }, parts[0], gap, parts.slice(1).join("___"));
    let tiles;
    tiles = choiceTiles(step.options, async (o, el) => {
      gap.textContent = o; gap.classList.add("filled");
      tiles.querySelectorAll(".tile").forEach(b => b.disabled = true);
      const r = await submit(o);
      if (r) { markChoice(tiles, el, r); gap.classList.add(r.correct ? "right" : "wrong"); if (!r.correct) gap.textContent = r.solution; }
    });
    return h("div", h("div.prompt", h("p.instruction", step.instruction), langChip(step.answer_lang), step.prompt ? C(step.prompt, "p.small.muted") : null, sentence), tiles);
  },

  eintippen(step, submit) {
    const input = h("input.type-in", { type: "text", autocomplete: "off", autocapitalize: "off", spellcheck: false, lang: step.lang || "",
      "aria-label": T("Your answer"), placeholder: T("Your answer"), onkeydown: e => { if (e.key === "Enter") check(); } });
    const keys = (step.keys || []).length ? h("div.special-keys", ...step.keys.map(k => h("button.key", { type: "button", translate: "no",
      onpointerdown: e => e.preventDefault(), onclick: () => insertAt(input, k) }, k))) : null;
    const btn = h("button.btn.big", { onclick: () => check() }, T("Check"));
    async function check() {
      if (!input.value.trim()) return input.focus();
      input.disabled = true; btn.disabled = true;
      const r = await submit(input.value);
      if (!r) { input.disabled = false; btn.disabled = false; return; }
      input.classList.add(r.correct ? "right" : "wrong");
    }
    setTimeout(() => input.focus(), 60);
    return h("div", promptBlock(step), h("div.type-area", input, keys, btn));
  },

  karteikarte(step, submit) {
    const card = h("button.flash", { onclick: () => flip() },
      h("div.flash-inner",
        h("div.flash-face.front", media(step), C(step.prompt, "div.flash-text"), h("span.small.muted", T("Tap to turn"))),
        h("div.flash-face.back", C(step.back, "div.flash-text"),
          step.lang ? h("span.speak-mini", { onclick: e => { e.stopPropagation(); speak(step.back, step.lang); } }, "🔊") : null)));
    const grade = h("div.grade-row", { hidden: true },
      h("button.btn.bad", { onclick: () => pick("wrong") }, "✗ ", T("Not yet")),
      h("button.btn.ghost", { onclick: () => pick("almost") }, "≈ ", T("Almost")),
      h("button.btn.good", { onclick: () => pick("correct") }, "✓ ", T("Knew it")));
    function flip() { card.classList.add("flipped"); grade.hidden = false; }
    async function pick(v) { grade.querySelectorAll("button").forEach(b => b.disabled = true); await submit(v); }
    return h("div", h("div.prompt", h("p.instruction", step.instruction), langChip(step.answer_lang)), card, grade);
  },

  paare(step, submit) {
    const colors = ["#4f8cff", "#ff922b", "#20c997", "#be4bdb", "#fcc419", "#ff6b6b"];
    const pairs = {}; // left id → right id
    let sel = null;
    const L = step.left.map(x => h("button.pair.left", { "data-id": x.id, translate: "no", onclick: () => pickL(x.id) },
      x.image ? h("img.pair-img", { src: x.image, alt: "" }) : null, x.emoji ? x.emoji + " " : "", x.text));
    const R = step.right.map(x => h("button.pair.right", { "data-id": x.id, translate: "no", onclick: () => pickR(x.id) }, x.text));
    const btn = h("button.btn.big", { disabled: true, onclick: () => check() }, T("Check"));
    const paint = () => {
      const used = Object.keys(pairs);
      L.forEach(b => { const i = used.indexOf(b.dataset.id); b.style.borderColor = i >= 0 ? colors[i % colors.length] : ""; b.classList.toggle("sel", sel === b.dataset.id); b.classList.toggle("paired", i >= 0); });
      R.forEach(b => { const l = used.find(k => pairs[k] === b.dataset.id); const i = used.indexOf(l); b.style.borderColor = i >= 0 ? colors[i % colors.length] : ""; b.classList.toggle("paired", i >= 0); });
      btn.disabled = used.length !== L.length;
    };
    function pickL(id) { if (pairs[id]) { delete pairs[id]; sel = null; } else sel = sel === id ? null : id; Sound.play("tap"); paint(); }
    function pickR(id) {
      const owner = Object.keys(pairs).find(k => pairs[k] === id);
      if (owner) { delete pairs[owner]; paint(); return; }
      if (!sel) return;
      pairs[sel] = id; sel = null; Sound.play("tap"); paint();
    }
    async function check() {
      btn.disabled = true;
      [...L, ...R].forEach(b => b.disabled = true);
      const r = await submit(pairs);
      if (!r) { [...L, ...R].forEach(b => b.disabled = false); btn.disabled = false; return; }
      L.forEach(b => {
        const ok = r.solution[b.dataset.id] === pairs[b.dataset.id];
        b.classList.add(ok ? "right" : "wrong");
        if (!ok) { const right = step.right.find(x => x.id === r.solution[b.dataset.id]); b.append(h("span.fix", " → ", right ? right.text : "")); }
      });
    }
    return h("div", h("p.instruction", step.instruction), h("div.pairs", h("div.col", ...L), h("div.col", ...R)), btn);
  },

  zuordnen(step, submit) { return dragSort(step, submit); },

  rechnen(step, submit) { return mathStep(step, submit); },
};

function insertAt(input, text) {
  const s = input.selectionStart ?? input.value.length, e = input.selectionEnd ?? input.value.length;
  input.value = input.value.slice(0, s) + text + input.value.slice(e);
  input.focus();
  input.setSelectionRange(s + text.length, s + text.length);
}

// ---------------------------------------------------------------- drag & drop (zuordnen)
function dragSort(step, submit) {
  const placed = {}; // chip id → target id
  let selected = null;
  const pool = h("div.dz-pool", { "data-target": "" });
  const chips = step.chips.map(c => h("button.chip-drag", { type: "button", "data-id": c.id, translate: "no" }, c.emoji ? c.emoji + " " : "", c.text));
  chips.forEach(ch => pool.append(ch));
  const zones = step.targets.map(t => h("div.dz", { "data-target": t.id },
    h("div.dz-title", { translate: "no" }, t.text), h("div.dz-body")));
  const btn = h("button.btn.big", { disabled: true, onclick: () => check() }, T("Check"));
  const wrap = h("div.dnd", h("p.instruction", step.instruction), pool, h("div.dz-grid" + (zones.length > 4 ? ".many" : ""), ...zones), btn);

  const moveTo = (chip, target) => {
    const id = chip.dataset.id;
    if (target) { placed[id] = target.dataset.target; target.querySelector(".dz-body").append(chip); }
    else { delete placed[id]; pool.append(chip); }
    chip.classList.remove("sel"); selected = null;
    btn.disabled = Object.keys(placed).length !== chips.length;
    pool.classList.toggle("empty", !pool.children.length);
    Sound.play("tap");
  };
  const zoneAt = (x, y) => {
    const el = document.elementFromPoint(x, y);
    if (!el) return undefined;
    const z = el.closest(".dz");
    if (z) return z;
    return el.closest(".dz-pool") ? null : undefined;
  };
  chips.forEach(chip => {
    chip.addEventListener("pointerdown", e => {
      if (chip.disabled) return;
      e.preventDefault();
      const r = chip.getBoundingClientRect();
      const start = { x: e.clientX, y: e.clientY };
      let ghost = null, over = null;
      const move = ev => {
        const dx = ev.clientX - start.x, dy = ev.clientY - start.y;
        if (!ghost && Math.hypot(dx, dy) > 6) {
          ghost = chip.cloneNode(true); ghost.classList.add("ghost");
          Object.assign(ghost.style, { width: r.width + "px", left: r.left + "px", top: r.top + "px" });
          document.body.append(ghost); chip.classList.add("dragging");
        }
        if (ghost) {
          ghost.style.transform = `translate(${dx}px, ${dy}px) rotate(-3deg)`;
          const z = zoneAt(ev.clientX, ev.clientY);
          if (over && over !== z) over.classList.remove("over");
          over = z || null; if (over) over.classList.add("over");
        }
      };
      const up = ev => {
        document.removeEventListener("pointermove", move);
        document.removeEventListener("pointerup", up);
        document.removeEventListener("pointercancel", up);
        if (over) over.classList.remove("over");
        chip.classList.remove("dragging");
        if (ghost) {
          ghost.remove();
          const z = zoneAt(ev.clientX, ev.clientY);
          if (z !== undefined) moveTo(chip, z);
        } else {                          // a tap: select, then tap a field
          if (selected === chip) { chip.classList.remove("sel"); selected = null; }
          else { chips.forEach(c => c.classList.remove("sel")); chip.classList.add("sel"); selected = chip; }
        }
      };
      document.addEventListener("pointermove", move);
      document.addEventListener("pointerup", up);
      document.addEventListener("pointercancel", up);
    });
    chip.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); chips.forEach(c => c.classList.remove("sel")); chip.classList.add("sel"); selected = chip; } });
  });
  zones.forEach(z => z.addEventListener("click", e => { if (selected && !e.target.closest(".chip-drag")) moveTo(selected, z); }));
  pool.addEventListener("click", e => { if (selected && !e.target.closest(".chip-drag")) moveTo(selected, null); });

  async function check() {
    btn.disabled = true; chips.forEach(c => c.disabled = true);
    const r = await submit(placed);
    if (!r) { chips.forEach(c => c.disabled = false); btn.disabled = false; return; }
    chips.forEach(c => {
      const ok = r.solution[c.dataset.id] === placed[c.dataset.id];
      c.classList.add(ok ? "right" : "wrong");
      if (!ok) { const t = step.targets.find(t => t.id === r.solution[c.dataset.id]); c.append(h("span.fix", " → ", t ? t.text : "")); }
    });
  }
  return wrap;
}

// ---------------------------------------------------------------- arithmetic
function fracEl(n, d) { return h("span.frac", h("span.num", String(n)), h("span.den", String(d))); }

function exprEl(expr) {
  return h("div.expr", { translate: "no" }, ...expr.map(t => {
    if (t && typeof t === "object" && t.frac) return fracEl(t.frac[0], t.frac[1]);
    if (t === "von") return h("span.op", I18N.tr(T("of")));
    return h("span" + (/^[+−×:=≈]$/.test(String(t)) ? ".op" : ".num-tok"), typeof t === "number" ? fmt(t, 6) : String(t));
  }));
}

function mathStep(step, submit) {
  const box = (label) => h("input.math-in", { type: "text", inputmode: "decimal", autocomplete: "off", "aria-label": label,
    onfocus: e => { active = e.target; }, onkeydown: e => { if (e.key === "Enter") check(); } });
  let active = null, inputs = [], area;
  if (step.input === "choice") {
    let tiles;
    tiles = choiceTiles(step.options, async (o, el) => { tiles.querySelectorAll(".tile").forEach(b => b.disabled = true); const r = await submit(o); if (r) markChoice(tiles, el, r); },
      o => /^\d+\/\d+$/.test(o) ? fracEl(...o.split("/")) : C(o));
    return h("div", h("div.prompt", h("p.instruction", step.instruction), step.expr.length ? exprEl(step.expr) : null), tiles);
  }
  if (step.input === "fraction") {
    inputs = [box(T("Numerator")), box(T("Denominator"))];
    area = h("span.frac.frac-in", h("span.num", inputs[0]), h("span.den", inputs[1]));
  } else if (step.input === "div_rest") {
    inputs = [box(T("Result")), box(T("Remainder"))];
    area = h("span.divrest", inputs[0], h("b", " R "), inputs[1]);
  } else {
    inputs = [box(T("Result"))];
    area = inputs[0];
  }
  active = inputs[0];
  const press = k => {
    const el = active || inputs[0];
    if (k === "⌫") el.value = el.value.slice(0, -1);
    else if (k === "→") { const i = inputs.indexOf(el); (inputs[i + 1] || inputs[0]).focus(); return; }
    else el.value += k;
    el.focus();
  };
  const keys = ["7", "8", "9", "4", "5", "6", "1", "2", "3", inputs.length > 1 ? "→" : ".", "0", "⌫"];
  const pad = h("div.numpad", ...keys.map(k => h("button.key", { type: "button", onpointerdown: e => e.preventDefault(), onclick: () => press(k) }, k)));
  const btn = h("button.btn.big", { onclick: () => check() }, T("Check"));
  async function check() {
    if (inputs.some(i => !i.value.trim())) return (inputs.find(i => !i.value.trim())).focus();
    const val = step.input === "number" ? inputs[0].value : inputs.map(i => i.value.trim());
    inputs.forEach(i => i.disabled = true); btn.disabled = true;
    const r = await submit(val);
    if (!r) { inputs.forEach(i => i.disabled = false); btn.disabled = false; return; }
    inputs.forEach(i => i.classList.add(r.correct ? "right" : "wrong"));
  }
  setTimeout(() => inputs[0].focus(), 60);
  return h("div.math", h("div.prompt", h("p.instruction", step.instruction), h("div.expr-row", exprEl(step.expr), area)), pad, btn);
}

// ---------------------------------------------------------------- shop
async function shopView() {
  let d;
  try { d = await api("me/shop"); } catch (e) { return toast(e.message, "bad"); }
  const accs = d.accounts.filter(a => a.spendable);
  const accIcon = k => (accs.find(a => a.key === k) || {}).icon || "🪙";
  const status = { pending: T("waiting for approval"), approved: T("approved"), rejected: T("declined"), failed: T("did not work") };
  screen("shop",
    h("h1", "🛍️ ", T("Shop")),
    h("div.balances.card", ...accs.map(a => h("div.balance", h("span.bal-ic", a.icon || "🪙"), h("b", fmt(d.balances[a.key], 1)), h("span.small.muted", a.name)))),
    d.offers.length ? h("div.shop-grid", ...d.offers.map(o => h("div.offer.card" + (o.can ? "" : ".cant"),
      h("div.offer-ic", o.icon), h("strong", o.name),
      h("div.price", accIcon(o.account) + " " + fmt(o.cost)),
      o.approval ? h("span.small.muted", "👪 ", T("Parents confirm")) : null,
      o.can ? h("button.btn", { onclick: () => redeem(o) }, T("Redeem")) : h("div.small.muted.reason", o.reason),
      !o.can && o.missing > 0 ? bar(o.cost - o.missing, o.cost) : null))) : h("p.muted", T("The shop is still empty.")),
    await avatarSpecials(),
    d.history.length ? h("section.card", h("h2", T("My wishes")), h("ul.history", ...d.history.map(r =>
      h("li", h("span", r.icon + " "), h("span.grow", r.name), h("span.small.status." + r.status, status[r.status] || r.status))))) : null);
  async function redeem(o) {
    if (!confirm(I18N.tr(T("Redeem {0} for {1}?")).replace("{0}", o.name).replace("{1}", fmt(o.cost)))) return;
    try {
      const r = await api("me/redeem", { method: "POST", body: { reward_id: o.id } });
      Sound.play("done");
      toast(r.status === "approved" ? T("Done – have fun!") : r.status === "pending" ? T("Sent to your parents") : T("That did not work"), r.status === "failed" ? "bad" : "good");
      shopView();
    } catch (e) { toast(e.message, "bad"); }
  }
}

// avatar specials in the shop: fun items that can only be earned (bought with coins)
async function avatarSpecials() {
  let d;
  try { d = await api("me/avatar"); } catch { return null; }
  const items = d.items.filter(i => i.rule && i.rule.cost);
  if (!items.length) return null;
  const a = d.avatar;
  const wear = async i => {
    const next = { ...a, items: { ...(a.items || {}), [i.slot]: i.id } };
    try { await api("me/avatar", { method: "POST", body: { avatar: next } }); Sound.play("right"); toast(T("Your avatar wears it now"), "good"); shopView(); }
    catch (e) { toast(e.message, "bad"); }
  };
  const buy = async i => {
    if (!confirm(I18N.tr(T("Buy {0} for {1} coins?")).replace("{0}", I18N.tr(i.name)).replace("{1}", i.rule.cost))) return;
    try { await api("me/avatar/buy", { method: "POST", body: { item: i.id } }); Sound.play("done"); confetti(); await wear(i); }
    catch (e) { toast(e.message, "bad"); }
  };
  return h("section.card", h("h2", "🧑‍🎨 ", T("Avatar specials")), h("p.small.muted", T("Only to earn: buy them with your coins and your avatar wears them.")),
    h("div.shop-grid", ...items.map(i => {
      const worn = (a.items || {})[i.slot] === i.id;
      return h("div.offer.card" + (i.unlocked || d.coins >= i.rule.cost ? "" : ".cant"),
        avatarSvg({ ...a, items: { ...(a.items || {}), [i.slot]: i.id } }, 84), h("strong", T(i.name)),
        i.unlocked ? (worn ? h("span.small.muted", "✓ ", T("You wear it")) : h("button.btn.small", { onclick: () => wear(i) }, T("Put on")))
          : [h("div.price", "🪙 " + i.rule.cost), d.coins >= i.rule.cost ? h("button.btn.small", { onclick: () => buy(i) }, T("Buy")) : bar(d.coins, i.rule.cost)]);
    })));
}

// ---------------------------------------------------------------- avatar editor
async function avatarView() {
  let d;
  try { d = await api("me/avatar"); } catch (e) { return toast(e.message, "bad"); }
  const a = JSON.parse(JSON.stringify(d.avatar));
  a.items = a.items || {};
  const preview = h("div.av-preview");
  const draw = () => preview.replaceChildren(avatarSvg(a, 200));
  const TABS = [["skin", T("Skin")], ["hair", T("Hair")], ["hairColor", T("Hair colour")], ["eyes", T("Eyes")], ["mouth", T("Mouth")],
    ["outfit", T("Clothes")], ["outfitColor", T("Colour")], ["items", T("Items")]];
  let tab = "skin";
  const tabs = h("div.av-tabs");
  const panel = h("div.av-panel");
  const ruleText = r => r.level ? T("From level {0}").replace("{0}", r.level)
    : r.badge ? T("With a badge") : r.cost ? T("Buy for {0} coins").replace("{0}", r.cost)
    : r.season ? T("Only in season") : "";
  const drawTabs = () => tabs.replaceChildren(...TABS.map(([k, n]) => h("button" + (tab === k ? ".on" : ""), { onclick: () => { tab = k; drawTabs(); drawPanel(); } }, n)));
  const drawPanel = () => {
    if (tab === "items") {
      panel.replaceChildren(...d.slots.map(slot => {
        const its = d.items.filter(i => i.slot === slot);
        return h("div.av-slot", h("h3", { "data-slot": slot }, slotName(slot)), h("div.av-opts",
          h("button.av-opt" + (!a.items[slot] ? ".on" : ""), { onclick: () => { delete a.items[slot]; draw(); drawPanel(); } }, "∅"),
          ...its.map(i => h("button.av-opt.item" + (a.items[slot] === i.id ? ".on" : "") + (i.unlocked ? "" : ".locked"),
            { title: i.unlocked ? i.name : ruleText(i.rule), onclick: () => pickItem(i) },
            avatarSvg(Object.assign({}, a, { items: Object.assign({}, a.items, { [slot]: i.id }) }), 64),
            h("span.small", i.name), i.unlocked ? null : h("span.lock-note", "🔒 ", ruleText(i.rule))))));
      }));
      return;
    }
    const opts = d.parts[tab];
    panel.replaceChildren(h("div.av-opts", ...opts.map(v => {
      const isColor = /^#/.test(v);
      const sample = isColor ? h("span.swatch", { style: { background: v } }) : avatarSvg(Object.assign({}, a, { [tab]: v }), 64);
      return h("button.av-opt" + (a[tab] === v ? ".on" : ""), { onclick: () => { a[tab] = v; draw(); drawPanel(); }, "aria-label": v }, sample);
    })));
  };
  async function pickItem(i) {
    if (!i.unlocked) {
      if (i.rule.cost && confirm(I18N.tr(T("Buy {0} for {1} coins?")).replace("{0}", I18N.tr(i.name)).replace("{1}", i.rule.cost))) {
        try { await api("me/avatar/buy", { method: "POST", body: { item: i.id } }); i.unlocked = true; Sound.play("done"); toast(T("Unlocked!"), "good"); }
        catch (e) { return toast(e.message, "bad"); }
      } else return toast(ruleText(i.rule));
    }
    a.items[i.slot] = i.id; draw(); drawPanel();
  }
  // emoji, eyes, mouth, label – the face of the avatar follows; parents see the emoji (sad, sick, angry: quietly told)
  const MOODS = [["😊", "happy", "grin", T("Good")], ["🤩", "big", "grin", T("Super")], ["😐", "round", "neutral", T("So-so")],
    ["😴", "sleepy", "neutral", T("Tired")], ["😕", "dizzy", "neutral", T("Confused")], ["😟", "big", "open", T("Worried")],
    ["😢", "sad", "sad", T("Sad")], ["🤢", "round", "wavy", T("I feel sick")], ["😠", "angry", "sad", T("Angry")]];
  let mood = d.mood || "";
  const feel = h("input.feel-in", { type: "text", maxlength: 200, value: d.mood_text || "", placeholder: T("e.g. tired, happy, a bit nervous …"),
    "aria-label": T("Today I feel …") });
  const moods = h("div.card.moods-card",
    h("div.moods", h("strong", T("How do you feel?")), ...MOODS.map(([ic, eyes, mouth, label]) =>
      h("button.mood" + (mood === ic ? ".on" : ""), { title: label, "aria-label": label, onclick: e => { a.eyes = eyes; a.mouth = mouth; mood = ic;
        e.currentTarget.parentNode.querySelectorAll(".mood").forEach(b => b.classList.toggle("on", b === e.currentTarget)); draw(); drawPanel(); feel.focus(); } }, ic))),
    h("label.feel", h("span", T("Today I feel …")), feel),
    h("span.small.muted", "🔒 ", T("Only your parents see this.")));
  draw(); drawTabs(); drawPanel();
  screen("avatar", h("h1", "🧑‍🎨 ", T("Me")), moods, h("div.av-editor", preview, h("div.av-side", tabs, panel)),
    h("div.row.center", h("button.btn.big", { onclick: save }, "💾 ", T("Save"))),
    h("div.row.center", h("button.btn.ghost", { onclick: changePin }, "🔑 ", T("Change my PIN"))),
    S.me.games ? botsSection() : null);
  async function save() {
    try { await api("me/avatar", { method: "POST", body: { avatar: a, mood_text: feel.value, mood } }); Sound.play("right"); toast(T("Saved"), "good"); go(""); }
    catch (e) { toast(e.message, "bad"); }
  }
}

// ---------------------------------------------------------------- own bots for the games (shared with the family or not)
const BOT_COLORS = ["#5b5bd6", "#d6336c", "#e8590c", "#0c8599", "#2f9e44", "#7048e8", "#f59f00", "#495057"];
const BOT_LEVELS = { easy: T("easy"), normal: T("normal"), hard: T("hard") };
function botBadge(b, size = 52) {
  return h("span.bot-av", { style: { width: size + "px", height: size + "px", fontSize: (size * .58) + "px", background: b.color || "var(--hover)" } }, b.emoji || "🤖");
}
function botsSection() {
  const sec = h("section.card.bots-sec");
  const load = async () => {
    let d; try { d = await api("community/bots"); } catch (e) { return sec.replaceChildren(h("p.bad", e.message)); }
    sec.replaceChildren(h("div.sec-head", h("h2", "🤖 ", T("My bots")), h("div.head-actions", h("button.btn", { onclick: () => botDialog(null, d.emojis, load) }, "+ ", T("New bot")))),
      h("p.small.muted", T("Make your own bots – they play with you in Tschau Sepp, Kartenkarussell and Texas Hold'em. Shared bots can play with your siblings too.")),
      d.bots.length ? h("div.bot-grid", ...d.bots.map(b => h("button.bot-tile", { onclick: () => b.mine ? botDialog(b, d.emojis, load) : toast(I18N.tr(T("A bot of {0}")).replace("{0}", b.owner || "?")) },
        botBadge(b), C(b.name, "strong"), h("span.small.muted", I18N.tr(BOT_LEVELS[b.level])),
        b.mine ? (b.shared ? h("span.chip.good", "👨‍👩‍👧 ", T("shared")) : null) : h("span.chip", I18N.tr(T("by {0}")).replace("{0}", b.owner || "?")))))
        : h("p.muted", T("No bot yet – make one!")));
  };
  load();
  return sec;
}
function botDialog(b, emojis, done) {
  const cur = b ? { ...b } : { name: "", emoji: "🤖", color: BOT_COLORS[0], level: "normal", shared: false };
  const preview = h("div.center"), name = h("input", { type: "text", maxlength: 24, value: cur.name, placeholder: I18N.tr(T("e.g. Robo Rita")) });
  const drawPrev = () => preview.replaceChildren(botBadge(cur, 84));
  const emo = h("div.bot-emojis", ...emojis.map(e => h("button" + (e === cur.emoji ? ".on" : ""), { type: "button", onclick: ev => { cur.emoji = e;
    emo.querySelectorAll("button").forEach(x => x.classList.toggle("on", x === ev.currentTarget)); drawPrev(); } }, e)));
  const col = h("div.row", ...BOT_COLORS.map(c => h("button.swatch-btn" + (c === cur.color ? ".on" : ""), { type: "button", style: { background: c }, "aria-label": c,
    onclick: ev => { cur.color = c; col.querySelectorAll("button").forEach(x => x.classList.toggle("on", x === ev.currentTarget)); drawPrev(); } })));
  const lvl = h("select", ...Object.entries(BOT_LEVELS).map(([k, n]) => h("option", { value: k, selected: k === cur.level }, I18N.tr(n))));
  const share = h("input", { type: "checkbox", checked: !!cur.shared });
  drawPrev();
  const m = modal(h("div.form", h("h2", "🤖 ", b ? T("Edit bot") : T("New bot")), preview,
    h("label.field", T("Name"), name), h("div.field", h("b", T("Look")), emo), h("div.field", h("b", T("Colour")), col),
    h("label.field", T("Plays"), lvl), h("label.check", share, T("Share with the family (siblings can play with it too)")),
    h("div.row", h("button.btn", { onclick: async () => {
      try { await api(b ? `community/bots/${b.id}` : "community/bots", { method: b ? "PUT" : "POST",
        body: { name: name.value, emoji: cur.emoji, color: cur.color, level: lvl.value, shared: share.checked } }); m.close(); toast(T("Saved"), "good"); done(); }
      catch (e) { toast(e.message, "bad"); }
    } }, "💾 ", T("Save")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")), h("span.grow"),
      b ? h("button.btn.small.bad", { onclick: async () => { if (!confirm(I18N.tr(T("Delete the bot «{0}»?")).replace("{0}", b.name))) return;
        try { await api(`community/bots/${b.id}`, { method: "DELETE" }); m.close(); done(); } catch (e) { toast(e.message, "bad"); } } }, T("Delete")) : null)));
  name.focus();
}

// ---------------------------------------------------------------- own PIN
// 1. the current PIN (checked like a login)  2. symbols or digits  3. new PIN (digits: twice)
function changePin() {
  const p = S.me.profile;
  const body = h("div.pin-change");
  const m = modal(body);
  body.addEventListener("cancel", e => { e.stopPropagation(); m.close(); });
  let old = "";
  const finish = async payload => {
    const r = await api("me/pin", { method: "POST", body: { old_pin: old, ...payload } });
    if (r.token) Auth.kid = r.token;                    // the new PIN ends the other logins – this device stays in
    S.me.profile = r.profile; m.close(); Sound.play("right"); toast(T("Your new PIN is saved"), "good");
  };
  const step1 = () => {
    if (!p.has_pin) return step2();
    const check = async pin => {
      await api("login", { method: "POST", body: { profile_id: p.id, pin } });   // throws «Wrong PIN»
      old = pin; step2();
    };
    body.replaceChildren(p.pin_kind === "symbols" && p.symbol_set
      ? symbolPad({ title: T("Your current PIN"), symbols: p.symbol_set, onSubmit: ids => check("sym:" + ids.join(",")) })
      : pinPad({ title: T("Your current PIN"), length: 4, maxLength: p.role === "kid" ? 4 : 8, onSubmit: check }));
  };
  const step2 = () => {
    body.replaceChildren(h("div.center", h("h2", T("What should your new PIN be?")),
      h("div.row.center.pin-kinds",
        h("button.btn.big", { onclick: stepSymbols }, "🐱 ", T("Symbols")),
        h("button.btn.big", { onclick: stepDigits }, "🔢 ", T("Digits"))),
      h("button.link", { onclick: () => m.close() }, T("Cancel"))));
  };
  const stepSymbols = () => {
    const pad = symbolPad({ mode: "set", cancel: false });
    body.replaceChildren(h("h2.center", T("Your new picture PIN")), pad, h("div.row.center",
      h("button.btn.ghost", { onclick: step2 }, "← ", T("Back")),
      h("button.btn", { onclick: async () => {
        const v = pad.value();
        if (v.symbols.length !== 4) return toast(T("Choose 4 symbols in your order – tap them or draw a line."), "bad");
        try { await finish({ pin_symbols: v.symbols, symbol_set: v.set }); } catch (e) { toast(e.message, "bad"); }
      } }, "💾 ", T("Save"))));
  };
  const stepDigits = () => {
    const n = p.role === "kid" ? 4 : 8;
    body.replaceChildren(pinPad({ title: T("Your new PIN"), length: 4, maxLength: n, cancel: false, onSubmit: async first => {
      body.replaceChildren(pinPad({ title: T("Once more, please"), length: 4, maxLength: n, cancel: false, onSubmit: async again => {
        if (again !== first) { toast(T("The two PINs are not the same – try again."), "bad"); return stepDigits(); }
        await finish({ pin: first });
      } }));
    } }));
  };
  step1();
}

function slotName(s) {
  return { background: T("Background"), hat: T("Hats"), hairclip: T("Hair clips"), eyewear: T("Glasses"), face: T("Face"), teeth: T("Braces"),
    ear: T("Ears"), neck: T("Neck"), pet: T("Pets") }[s] || s;
}

// ---------------------------------------------------------------- family view
async function familyView() {
  let d;
  try { d = await api("family"); } catch (e) { return toast(e.message, "bad"); }
  const showAll = d.visibility === "all", showPct = d.visibility !== "goal";
  screen("family",
    h("h1", "👨‍👩‍👧 ", T("Family")),
    d.family_goal ? familyGoalCard(d.family_goal) : null,
    showPct ? h("div.family-grid", ...d.members.map(m => h("div.card.member" + (d.winner === m.profile.id ? ".winner" : ""),
      d.winner === m.profile.id ? h("div.crown", { title: T("Winner of last week") }, "👑") : null,
      avatarSvg(m.profile.avatar, 84), C(m.profile.name, "h2"),
      ring(m.today_percent, 100, { size: 96, stroke: 10, label: h("span", h("b", m.today_percent + " %"), h("br"), h("span.small.muted", T("today"))) }),
      h("dl.stats",
        h("dt", T("This week")), h("dd", m.week_percent + " %"),
        h("dt", "🔥 " + I18N.tr(T("Streak"))), h("dd", String(m.streak)),
        h("dt", T("Learning progress")), h("dd", m.progress + " %"),
        m.chores && m.chores.reliability != null ? [h("dt", "🧹 " + I18N.tr(T("Chores"))), h("dd", fmt(m.chores.reliability) + " %")] : null,
        showAll && m.level ? [h("dt", "Level"), h("dd", String(m.level))] : null)))) : null,
    h("p.small.muted.center", T("Compared is the effort towards each one's own goal – not the raw points.")),
    await councilSection(), await pollsSection(), await wichtelnSection(), await historySection());
}

// ---------------------------------------------------------------- the games (own menu item)
async function gamesView() {
  const cards = [canPlay("quiz") ? await quizCard() : null, canPlay("bingo") ? await bingoCard() : null, canPlay("song") ? await songFamilyCard() : null,
    canPlay("tschau") ? await cardsFamilyCard("tschau") : null, canPlay("karussell") ? await cardsFamilyCard("karussell") : null,
    canPlay("domino") ? await dominoFamilyCard() : null, canPlay("poker") ? await pokerFamilyCard() : null, arcadeCard()].filter(Boolean);
  screen("games", h("h1", "🎲 ", T("Games")), ...cards);
}

// ---------------------------------------------------------------- my devices (Home Assistant)
function devicesCard() {
  const box = h("div.dev-grid", h("p.small.muted", "…"));
  const ICON = { light: "💡", switch: "🔌", input_boolean: "🔘", fan: "🌀", cover: "🪟", scene: "🎬", script: "▶️" };
  const draw = list => box.replaceChildren(...list.map(d => {
    const act = async (action, value) => {
      try { const r = await api(`me/devices/${encodeURIComponent(d.entity_id)}`, { method: "POST", body: { action, value } }); Sound.play("tap"); draw(r.devices); }
      catch (e) { toast(e.message, "bad"); }
    };
    const ctl = d.domain === "cover" ? h("div.row", h("button.btn.small", { onclick: () => act("open") }, "▲"), h("button.btn.small.ghost", { onclick: () => act("stop") }, "■"), h("button.btn.small", { onclick: () => act("close") }, "▼"))
      : ["scene", "script"].includes(d.domain) ? h("button.btn.small", { onclick: () => act("run") }, "▶ ", T("Start"))
      : h("button.dev-toggle" + (d.on ? ".on" : ""), { disabled: !d.available, onclick: () => act(d.on ? "off" : "on"), "aria-label": d.on ? T("Off") : T("On") }, h("i"));
    const slider = d.dimmable ? h("input.dev-dim", { type: "range", min: 1, max: 100, value: d.brightness || 0, disabled: !d.available,
      onchange: e => act("brightness", +e.target.value) }) : null;
    return h("div.dev-tile" + (d.on ? ".on" : "") + (d.available ? "" : ".off"), h("div.row", h("span.big-ic", ICON[d.domain] || "🏠"), C(d.name, "strong.grow"), ctl), slider,
      d.available ? null : h("span.small.muted", T("not reachable")));
  }));
  api("me/devices").then(l => l.length ? draw(l) : box.closest("section")?.remove()).catch(() => box.closest("section")?.remove());
  return h("section.card", h("h2", "🏠 ", T("My devices")), box);
}

// ---------------------------------------------------------------- course catalogue (language courses, general knowledge)
async function coursesView() {
  let list = [];
  try { list = await api("me/courses"); } catch (e) { return toast(e.message, "bad"); }
  const LEVELS = { A1: T("Beginner"), A2: T("Basics"), B1: T("Advanced") };
  const groups = new Map();
  for (const c of list) { const k = c.subject.key; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(c); }
  const toggle = async (c, on) => {
    try { await api(`me/courses/${encodeURIComponent(c.id)}`, { method: "POST", body: { on } }); }
    catch (e) { return toast(e.message, "bad"); }
    if (on) { Sound.play("done"); go("pack/" + encodeURIComponent(c.id)); } else coursesView();
  };
  screen("courses", { back: () => go("") }, h("h1", "🌍 ", T("Language courses & more")),
    h("p.muted", T("Choose a language and your level – the units unlock one after the other. Everybody can learn: children and adults.")),
    list.length ? [...groups.values()].map(cs => h("section.card.course", { style: { "--c": cs[0].subject.color } },
      h("h2", cs[0].subject.icon + " ", I18N.tr(cs[0].subject.name)),
      h("div.course-levels", ...cs.sort((a, b) => String(a.level).localeCompare(String(b.level))).map(c => h("div.course-level" + (c.on ? ".on" : ""),
        h("strong", { translate: "no" }, c.level), LEVELS[c.level] ? h("span.small", I18N.tr(LEVELS[c.level])) : null,
        C(c.description || c.title, "span.small.muted"),
        h("span.small.muted", c.units + " " + I18N.tr(T("units")) + " · " + c.cards + " " + I18N.tr(T("cards"))),
        c.on ? h("div.row", h("button.btn.small", { onclick: () => go("pack/" + encodeURIComponent(c.id)) }, "▶ ", T("Continue")),
                 h("button.btn.small.ghost", { onclick: () => toggle(c, false) }, T("Remove")))
             : h("button.btn.small", { onclick: () => toggle(c, true) }, "+ ", T("Start")))))))
      : h("p.muted", T("No courses yet.")));
}

boot();
