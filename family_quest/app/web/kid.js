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
  // opened in Home Assistant with the child's own Home Assistant user: logged in without PIN (also instead of another
  // profile still logged in on this device) – not again in this tab after «Log out» (haKidOff)
  if (S.info.ha_kid && !haKidOff() && !/^#\/?as\//.test(location.hash)) await haKidLogin().catch(() => {});
  window.addEventListener("hashchange", route);
  ["pointerdown", "keydown"].forEach(ev => document.addEventListener(ev, idleReset, { passive: true }));
  if ("serviceWorker" in navigator) {
    if (location.pathname.includes("/hassio_ingress/")) {
      // inside Home Assistant: no offline cache – the address changes per session, an old cache can leave the page black
      navigator.serviceWorker.getRegistrations().then(rs => rs.forEach(r => r.unregister())).catch(() => {});
    } else if (location.protocol === "https:") navigator.serviceWorker.register("sw.js").catch(() => {});
  }
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
  if (S.sheet) S.sheet.close();                          // a game card opened from its tile (gamesView)
  if (tableNote.box) closeTableNote();                  // «somebody opened a table»: gone on every navigation (also into that table)
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
  if (view === "deals") return dealsView(arg);                 // deals (deals.js)
  if (view === "board" && arg) return boardView(+arg);
  if (view === "games") return gamesView();
  if (view === "quiz") return quizView();
  if (view === "quizzes") return quizzesView();
  if (view === "courses") return coursesView();
  if (view === "bingo") return bingoView();
  if (view === "poker") return pokerView();
  if (view === "song") return songView();
  if (view === "tschau" || view === "karussell") return cardsView(view);
  if (view === "domino") return dominoView();
  if (view === "paarjagd") return paarjagdView();
  if (view === "werbinich") return werbinichView();
  if (view === "kartenlauf") return kartenlaufView();
  if (view === "stadtland") return stadtlandView();
  if (view === "zeichnen") return zeichnenView();
  if (view === "wuerfel") return wuerfelView();
  if (view === "heimwaerts") return heimwaertsView();
  if (view === "jump") return jumpView();
  if (view === "sternlauf") return sternlaufView();
  if (view === "snack") return snackView();
  if (view === "verkehr") return verkehrView();
  if (view === "langstrecke") return langstreckeView();
  if (view === "klatsch") return klatschView();
  if (view === "verboten") return verbotenView();
  if (view === "jass") return jassView();
  if (view === "werwolf") return werwolfView();
  if (view === "schach") return schachView(arg);
  if (view === "dorfmarkt") return dorfmarktView();
  if (view === "escape") return escapeView();
  if (view === "stempeljagd") return stempeljagdView();
  if (view === "arcade") return arcadeView(arg);
  if (view === "deck") return arg ? deckView(+arg) : decksView();
  if (view === "stories") return storiesView();
  if (view === "codelab") return S.me.codelab ? codelabView() : go("courses");          // 💡 Code Workshop (codelab.js) – dev channel
  if (view === "advgames") return canPlay("adventuregame") && S.me.stories !== false ? adventureGamesView() : go("games");   // stories.js
  return dashboardView();
}

const go = path => { if (location.hash === "#/" + path) route(); else location.hash = "#/" + path; };

async function loadMe() {
  S.me = await api("me");
  S.profile = S.me.profile;
  // deals (deals.js): the menu entry only when this profile may trade, a badge for offers waiting for an answer
  window.FQ_DEALS_OFF = !(S.me.deals && S.me.deals.on);
  window.FQ_NAV_BADGES = { deals: S.me.deals ? S.me.deals.turn || 0 : 0 };
  window.FQ_STORIES = S.me.stories !== false;           // adventure books switched off for this child: no menu entry
  if (S.me.prank) setTimeout(() => inkOverlay(S.me.prank), 400);     // somebody threw an ink bomb meanwhile
  idleReset();
}

// login with the Home Assistant user of a child (api/kid.py ha-login): only the children's app, never the parent area
const haKidOff = () => { try { return sessionStorage.getItem("fq.ha.off") === "1"; } catch { return false; } };
async function haKidLogin() {
  try { sessionStorage.removeItem("fq.ha.off"); } catch {}
  const r = await api("ha-login", { method: "POST" });
  if (!r.token) return false;
  Auth.kid = r.token; Auth.parent = "";
  return true;
}

function logout() {
  if (S.info && S.info.ha_kid) { try { sessionStorage.setItem("fq.ha.off", "1"); } catch {} }     // no automatic login right away
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
      h("span.grow", h("strong", C(x.title)), h("br"), txt, what ? [h("br"), h("span.small.muted", what)] : null,
        x.game ? [h("br"), h("span.small.ftg-line", x.game.icon + " ", C(ftGameLine(x.game)))] : null));     // FamilyTime: its game (community.js)
  });
}

// which games this child may play (parent area › Games – per game and person; a game with a price once bought / rented)
const canPlay = game => !!(S.me && (S.me.games_list || []).includes(game));
// locked for this child, but a parent opened a family table of it – that table can be joined (familyquest/services.parent_tables)
const tableOnly = game => !!(S.me && (S.me.games_tables || []).includes(game));
// a game with a price this child has not bought / rented (yet): {game, price, rent, period, …} (familyquest/gamepasses.py)
const lockedGame = game => ((S.me && S.me.games_locked) || []).find(g => g.game === game) || null;
// locked, but free tries are left (or the child sits at a table on a try): {left, member} (familyquest/services.trial_games)
const trialGame = game => (S.me && S.me.games_trial && S.me.games_trial[game]) || null;
const triesText = n => I18N.tr(n === 1 ? T("1 free try") : T("{0} free tries")).replace("{0}", n);

// ---------------------------------------------------------------- game battery (familyquest/battery.py) and party mode
// starting a game costs one charge segment – joining a table of somebody else is free; empty: recharge for coins
const battery = () => (S.me && S.me.battery) || null;
const batteryShown = () => { const b = battery(); return !!(b && (b.on || b.party)); };
const batteryEmpty = () => { const b = battery(); return !!(b && !b.free && b.charge <= 0); };
const partyOn = () => !!(S.me && S.me.party);

/** The battery strip (games page, game corner, the card of a game): segments, what a start costs, «Recharge». */
function batteryBar(compact = false) {
  const b = battery();
  if (!batteryShown()) return null;
  let text, sub = null, btn = null;
  if (b.party) { text = ["🎉 ", T("Party: starting games costs nothing")]; }
  else if (b.free) { text = b.forever || !b.until ? ["🔋 ", T("Unlimited game energy")] : ["🔋 ", I18N.tr(T("Unlimited game energy")) + " · " + untilWhen(b.until)]; }
  else if (b.charge <= 0) {
    text = ["🪫 ", T("Battery empty")];
    sub = T("You can still join a table of somebody else. To start a game yourself, recharge your battery.");
  } else {
    text = [I18N.tr(T("{0} of {1} charged")).replace("{0}", b.charge).replace("{1}", b.cap)];
    sub = compact ? T("Starting costs 🔋1") : T("Starting a game costs 🔋1 – joining a table is free.");
  }
  if (!b.free && b.charge < b.cap) btn = h("button.btn.small" + (b.charge <= 0 ? "" : ".ghost") + ".bat-recharge", { onclick: rechargeBattery },
    "⚡ ", T("Recharge"), b.cost > 0 ? " · " + b.cost + " 🪙" : "");
  return h("div.bat-bar" + (b.charge <= 0 && !b.free ? ".empty" : "") + (compact ? ".compact" : ""), batteryIcon(b, !compact),
    h("div.grow.bat-text", h("strong", ...text), sub ? h("div.small.muted", sub) : null), btn);
}

/** One battery per screen: the chip in the head of the games page; the card of a game and the game corner only say
 *  what a start costs – the full strip with «Recharge» only when the battery is empty. */
function batteryHint() {
  const b = battery();
  if (!batteryShown() || b.free) return null;
  if (b.charge <= 0) return h("div.card.bat-sheet", batteryBar(true));
  return h("p.small.muted.bat-hint", batteryIcon(b), " ", I18N.tr(T("{0} of {1} charged")).replace("{0}", b.charge).replace("{1}", b.cap), " · ", T("Starting costs 🔋1"));
}

/** Recharge the battery to full for coins – a confirm dialog first. `then`: what comes after (the start dialog of a game). */
function rechargeBattery(then = null) {
  const b = battery();
  if (!b) return;
  if (typeof then !== "function") then = null;
  const me = S.me || {}, coins = Math.floor(me.coins_available ?? (me.balances || {}).coins ?? 0), short = b.cost > coins;   // without deal reservations
  const m = modal(h("div.form.center.bat-dialog", h("h2", "⚡ ", T("Recharge your game battery")), batteryIcon(b, true),
    then ? h("p.bat-why", "🪫 ", T("Your battery is empty – recharge it to start this game.")) : null,
    h("p", b.cost > 0 ? I18N.tr(T("Recharge to full ({0} segments) for {1} coins?")).replace("{0}", b.cap).replace("{1}", b.cost)
      : I18N.tr(T("Recharge to full ({0} segments) – it costs nothing.")).replace("{0}", b.cap)),
    h("p.small.muted", "🪙 ", I18N.tr(T("You have {0} coins")).replace("{0}", coins)),
    short ? h("p.bad", T("Not enough coins")) : null,
    h("div.row.center", h("button.btn.big", { disabled: short, onclick: async () => {
      m.close();
      try {
        const r = await api("me/battery/recharge", { method: "POST" });
        S.me.battery = r.battery;
        S.me.coins_available = r.coins;
        Sound.play("done"); toast(T("Game battery recharged"), "good");
      } catch (e) { toast(e.message, "bad"); }
      try { S.me = await api("me"); } catch {}
      route();
      if (then && !batteryEmpty()) then();
    } }, "⚡ ", T("Recharge")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel"))),
    short && then ? h("p.small.muted", T("You can still join a table of somebody else. To start a game yourself, recharge your battery.")) : null));
}
// starting a game costs a segment: with an empty battery the start dialogs of all games ask to recharge first (instead
// of a refusal after filling in the dialog) – joining a table of somebody else does not go through them
for (const k of Object.keys(window).filter(k => /(StartDialog|SoloDialog)$/.test(k) && typeof window[k] === "function")) {
  const start = window[k];
  window[k] = (...a) => batteryEmpty() ? rechargeBattery(() => start(...a)) : start(...a);
}
// a start refused because the battery is empty (familyquest/api: 403): offer to recharge right away
window.FQ_BATTERY_EMPTY = async () => { try { S.me = await api("me"); } catch {} if (batteryEmpty() && !document.querySelector(".bat-dialog")) rechargeBattery(); };

/** Party mode of the parents: a festive banner on the start page and the games page. */
function partyBanner() {
  const p = S.me && S.me.party;
  if (!p) return null;
  const what = [p.unlock ? T("all games open") : null, p.battery ? T("starting is free") : null, p.limits ? T("no game time limit") : null].filter(Boolean);
  return h("section.card.banner.party-banner", h("span.big-ic", "🎉"),
    h("div.grow", h("strong", T("Party mode"), p.until ? " " + untilWhen(p.until) : ""), what.length ? h("div.small", what.map(t => I18N.tr(t)).join(" · ")) : null),
    h("span.big-ic.party-ball", "🪩"));
}
// the Disco design while the party runs for this child (or an own design of the parents with the disco look)
const discoTheme = () => (S.me && S.me.party && S.me.party.theme) || (S.info && S.info.season && S.info.season.vis === "disco" && seasonOn() ? S.info.season : null);

// somebody opened a family table: a note slides into the header (not while a game or a lesson fills the screen)
const tableNote = { seen: null, box: null, timer: null };
function tablesSeen() {
  if (!tableNote.seen) { try { tableNote.seen = JSON.parse(localStorage.getItem("fq.tables.seen." + S.me.profile.id)) || []; } catch { tableNote.seen = []; } }
  return tableNote.seen;
}
function closeTableNote() {
  const box = tableNote.box; clearTimeout(tableNote.timer); tableNote.box = null;
  if (box) { box.classList.remove("on"); setTimeout(() => box.remove(), 300); }
}
function showTableNote(t) {
  tableNote.box?.remove(); clearTimeout(tableNote.timer);
  const close = closeTableNote;
  // one compact line below the header – ☰, the clock and the title stay visible
  const box = h("div.table-note", { role: "status", "data-route": t.route },
    h("span.table-note-ic", t.icon),
    // short enough for one line on a phone: «Werewolves · Mia» – the whole sentence as tooltip / for screen readers
    h("span.table-note-txt", { title: I18N.tr(T("{0} opened a table: {1}")).replace("{0}", t.host || "?").replace("{1}", I18N.tr(t.title)),
      "aria-label": I18N.tr(T("{0} opened a table: {1}")).replace("{0}", t.host || "?").replace("{1}", I18N.tr(t.title)) },
      h("strong", I18N.tr(t.title)), " · ", C(t.host || "?")),
    // «Join» seats the child at once – the game opens already joined, without asking again
    h("button.btn.small", { onclick: async () => {
      close();
      if (t.join) { try { await api(t.join, { method: "POST" }); } catch (e) { toast(e.message, "bad"); } }
      go(t.route);
    } }, "▶ ", T("Join")),
    h("button.icon-btn", { title: T("Close"), "aria-label": T("Close"), onclick: close }, "✕"));
  const top = document.querySelector(".top");
  box.style.top = Math.max(8, Math.round(top ? top.getBoundingClientRect().bottom : 0) + 6) + "px";
  document.body.append(box); tableNote.box = box;
  requestAnimationFrame(() => box.classList.add("on"));
  try { Sound.play("turn"); if (Sound.on && navigator.vibrate) navigator.vibrate([80, 60, 80]); } catch {}
  tableNote.timer = setTimeout(close, 10000);
}
setInterval(async () => {
  if (!Auth.kid || !S.me || S.lesson || document.hidden || document.querySelector(".quiz-full, .arcade-full")) return;
  let list; try { list = await api("community/tables"); } catch { return; }
  const seen = tablesSeen(), fresh = list.filter(t => !seen.includes(t.key));
  if (!fresh.length) return;
  seen.push(...fresh.map(t => t.key)); seen.splice(0, Math.max(0, seen.length - 60));
  try { localStorage.setItem("fq.tables.seen." + S.me.profile.id, JSON.stringify(seen)); } catch {}
  if (!location.hash.includes(fresh[0].route)) showTableNote(fresh[0]);
}, 8000);

// invitations to a duel (Tic-Tac-Toe or Ping-Pong on two devices) pop up wherever the child is in the app
let duelSeen = 0;
setInterval(async () => {
  if (!Auth.kid || !S.me || !(canPlay("ttt") || canPlay("pingpong")) || S.lesson || document.hidden || /arcade\/(ttt|pingpong)/.test(location.hash)) return;
  let d; try { d = await api("community/duel"); } catch { return; }
  if (!d || d.status !== "invite" || d.host || d.id === duelSeen) return;
  duelSeen = d.id;
  try { Sound.play("tap"); } catch {}
  const other = d.names.X, pong = d.kind === "pong";
  const m = modal(h("div.form.center", h("h2", pong ? "🏓 " : "⭕ ", pong ? T("Ping-Pong") : T("Tic-Tac-Toe")),
    h("p", I18N.tr(pong ? T("{0} invites you to Ping-Pong") : T("{0} invites you to Tic-Tac-Toe")).replace("{0}", other)),
    h("div.row.center", h("button.btn.big", { onclick: async () => { m.close(); try { await api("community/duel/accept", { method: "POST" }); } catch {} S.arcadeJoin = pong ? "pingpong" : "ttt"; go(pong ? "arcade/pingpong" : "arcade/ttt"); } }, "▶ ", T("Play")),
      h("button.btn.ghost", { onclick: async () => { m.close(); try { await api("community/duel/decline", { method: "POST" }); } catch {} } }, T("No thanks")))));
}, 5000);
// invitations to a Ping-Pong doubles table (familyquest/pong4.py) – same popup as for a duel
let pong4Seen = 0;
setInterval(async () => {
  if (!Auth.kid || !S.me || !canPlay("pingpong") || S.lesson || document.hidden || S.p4Open) return;
  let d; try { d = await api("community/pong4"); } catch { return; }
  if (!d || d.status !== "lobby" || d.seats[d.me].state !== "invite" || d.seats[d.me].inv === pong4Seen) return;
  pong4Seen = d.seats[d.me].inv;                       // a new invitation (also to the same table) pops up again
  try { Sound.play("tap"); } catch {}
  const m = modal(h("div.form.center", h("h2", "🏓 ", T("Doubles (2 against 2)")),
    h("p", I18N.tr(T("{0} invites you to Ping-Pong doubles")).replace("{0}", d.seats.A1.name)),
    h("p.small.muted", I18N.tr(d.team === "A" ? T("You play in the team of the host.") : T("You play against the host."))),
    h("div.row.center", h("button.btn.big", { onclick: async () => { m.close(); try { await api("community/pong4/accept", { method: "POST" }); } catch {} S.pong4Online = true; S.arcadeJoin = "pingpong"; go("arcade/pingpong"); } }, "▶ ", T("Play")),
      h("button.btn.ghost", { onclick: async () => { m.close(); try { await api("community/pong4/decline", { method: "POST" }); } catch {} } }, T("No thanks")))));
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
function discoScene() {
  return h("div.scn.disco-scn", { "aria-hidden": "true" }, h("span.disco-ball", "🪩"), h("i.spot.s1"), h("i.spot.s2"), h("i.spot.s3"));
}
function seasonScene() {
  if (discoTheme()) return discoScene();
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
  const se = discoTheme() || (S.info && S.info.season);
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
  const se = discoTheme() || (S.info && S.info.season);
  const head = h("header.top.fq-head" + (se && (seasonOn() || discoTheme()) ? ".sc" : ""), { style: se && se.accent ? { "--season": se.accent } : null },
    seasonScene(),
    h("div.head-row" + (opts.back ? ".has-back" : ""),
      h("button.icon-btn.menu-btn", { title: T("Menu"), "aria-label": T("Menu"), onclick: () => openDrawer(active) }, "☰",
        (window.FQ_NAV_BADGES || {}).deals ? h("span.deal-badge", String(window.FQ_NAV_BADGES.deals)) : null),
      // load everything anew (e.g. a pet just bought, a game somebody opened)
      h("button.icon-btn.refresh-btn", { title: T("Refresh"), "aria-label": T("Refresh"), onclick: () => location.reload() }, "⟳"),
      opts.back ? h("button.icon-btn.back-btn", { title: T("Back"), "aria-label": T("Back"), onclick: opts.back }, "←") : null,
      h("button.me", { onclick: () => go("avatar"), title: T("Me") },
        avatarSvg(me.profile.avatar, 44),
        h("span.me-text", C(me.profile.name, "strong"), h("span.level-chip", "Level " + me.level.level))),
      h("button.streak", { type: "button", title: T("Days in a row with the daily goal"), onclick: () => toast(I18N.tr(T("Days in a row with the daily goal")) + ": " + me.streak) }, "🔥 ", h("b", String(me.streak))),
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
  document.body.classList.toggle("disco", !!discoTheme());      // party mode: the Disco design (shared/base.css)
  app.replaceChildren(h("div.screen", topBar(active, opts), h("main.content", ...content)));
  if (S.keepScroll != null) { window.scrollTo(0, S.keepScroll); S.keepScroll = null; } else window.scrollTo(0, 0);
  watchCommunity(active);
}

// the start page, «Games» and «Family» update themselves when somebody opens a game, a table or a vote
let _commTimer = null;
function watchCommunity(active) {
  clearInterval(_commTimer);
  if (!["home", "games", "family"].includes(active)) return;
  const at = location.hash;
  _commTimer = setInterval(async () => {
    if (location.hash !== at || document.hidden || S.lesson || document.querySelector(".modal-back, .quiz-full")) return;
    // somebody is typing (e.g. an idea for the family council): do not draw the page anew under their fingers
    const typing = [...document.querySelectorAll("main.content input[type=text], main.content textarea")].some(e => e.value.trim())
      || ["INPUT", "TEXTAREA", "SELECT"].includes((document.activeElement || {}).tagName);
    if (typing) return;
    let c;
    try { c = await api("me/community"); } catch { return; }
    if (location.hash !== at || !S.me) return;
    if (JSON.stringify(c) === JSON.stringify(S.me.community)) return;
    S.me.community = c;
    S.keepScroll = window.scrollY;
    await route();
    S.keepScroll = null;                                          // used up by screen() – or the page did not draw one
  }, 6000);
}

// ---------------------------------------------------------------- profiles
async function profilesView() {
  let profiles = [];
  try { profiles = await api("profiles"); } catch (e) { return fatal(e); }
  const kids = profiles.filter(p => p.role === "kid"), parents = profiles.filter(p => p.role === "parent");
  const tile = p => h("button.profile-tile", { onclick: () => login(p) }, avatarSvg(p.avatar, 120),
    C(p.name, "strong"), p.has_pin ? h("span.lock", { title: T("With PIN") }, "🔒") : null);
  const parentBtn = h("a.btn.ghost.parent-link", { href: "eltern" }, "🔐 ", T("Parent area"));
  const hk = S.info.ha_kid;
  const body = h("div.profiles-screen",
    h("div.row.profiles-head", h("h1.grow", T("Log in")), themeBtn(), langPicker()),
    hk ? h("div.center.ha-kid-login", h("button.btn.big", { onclick: async () => {
      try { if (await haKidLogin()) { Sound.play("tap"); location.hash = "#/"; route(); } } catch (e) { toast(e.message, "bad"); }
    } }, "🏠 ", I18N.tr(T("Log in as {0}")).replace("{0}", hk.name))) : null,
    S.info.setup_needed
      ? h("div.card.welcome", h("h2", T("Welcome to Family Quest!")), h("p", T("A parent sets up the profiles first.")),
          h("a.btn.big", { href: "eltern" }, T("Set up now")))
      : null,
    kids.length ? h("div.profile-grid", ...kids.map(tile)) : (!S.info.setup_needed ? h("p.muted.center", T("No child profile yet – add one in the parent area.")) : null),
    parents.length ? h("div.parents-row", h("span.muted", T("Learn along:")), ...parents.map(p =>
      h("button.parent-chip", { onclick: () => login(p) }, avatarSvg(p.avatar, 36), C(p.name)))) : null,
    parentBtn);
  app.replaceChildren(body);
  parentBtn.href = await parentAreaHref();
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

// the subjects (packs) of a profile as tiles: tap = the pack with its path, ▶ = go on with the next unit right away.
// Parents see every pack – drafts and switched-off ones marked – to try them out.
const STATUS_BADGE = { draft: () => "📝 " + I18N.tr(T("Draft")), disabled: () => "⏸ " + I18N.tr(T("Switched off")) };
function subjectGrid(me, withStart = false) {
  if (!me.subjects.length) return h("p.muted", T("No subjects active yet – a parent can switch on packs."));
  return h("div.subject-grid", ...me.subjects.map(s => {
    const tile = h("button.subject" + (s.status && s.status !== "active" ? ".trial" : ""), { style: { "--c": s.color }, onclick: () => go("pack/" + encodeURIComponent(s.pack)) },
      h("span.subject-ic", s.icon),
      h("span.subject-body",
        C(s.title, "strong"),
        STATUS_BADGE[s.status] ? h("span.small.status-badge", STATUS_BADGE[s.status]()) : null,
        h("span.row.small", stars(Math.round(5 * s.stars / Math.max(1, s.max_stars))), h("span.muted", s.percent + " %")),
        s.next ? h("span.small.next", T("Next:"), " ", C(s.next.title)) : h("span.small.next", "🏆 ", T("All done!")),
        s.due ? h("span.due", s.due + " " + T("to repeat")) : null));
    if (!withStart) return tile;
    return h("div.subject-wrap", tile, h("button.btn.small.subject-go", { style: { "--c": s.color }, title: T("Start"),
      onclick: () => startLesson({ mode: "path", pack: s.pack, unit: s.next ? s.next.id : undefined }) }, "▶ ", s.next ? T("Continue") : T("Repeat")));
  }));
}

// ---------------------------------------------------------------- dashboard
function dashboardView() {
  const me = S.me;
  const goal = me.daily_goal, xp = me.xp_today;
  const met = xp >= goal;
  const today = h("section.card.today",
    ring(xp, goal, { size: 132, stroke: 14, color: met ? "var(--good)" : "var(--accent)",
      label: h("span", h("b.big", fmt(xp)), h("br"), h("span.small.muted", "/ " + fmt(goal) + " XP"),
        h("br"), h("span.small.xp-total", { title: T("All XP so far") }, I18N.tr(T("Total {0} XP")).replace("{0}", fmt(me.level.xp)))) }),
    h("div.today-text",
      h("h2", met ? T("Daily goal reached! 🎉") : T("Today's goal")),
      h("p.muted", met ? T("Everything extra counts for your level.") : I18N.tr(T("Collect {0} XP today – every lesson and every right answer counts.")).replace("{0}", fmt(goal))),
      learnUp() ? null : h("button.btn.big", { onclick: () => startLesson({ mode: "daily" }) }, "▶ ", T("Daily lesson"))));

  const subjects = h("section",
    h("div.row", h("h2.grow", T("Subjects")), h("button.btn.small.ghost", { onclick: () => go("courses") }, "🌍 ", T("Language courses & more"))),
    subjectGrid(me));
  const sections = [...(me.profile.crown ? [h("section.card.banner.crown-banner", h("span.big-ic", "👑"), h("strong", T("Today you wear the crown!")))] : []),
    ...(me.weather ? [h("section.card.banner.weather-banner", h("span.weather-big", me.weather.icon),
      h("div", h("div.small.muted", T("Your weather today")), me.weather.name ? h("strong", I18N.tr(me.weather.name)) : null))] : []),
    ...(me.weather_alarm && me.weather_alarm.hints.length ? [h("section.card.banner.alarm-banner",
      h("span.big-ic", me.weather_alarm.now ? me.weather_alarm.now.icon : "🌂"),
      h("div.grow", ...me.weather_alarm.hints.map(x => h("div", x.icon, " ", C(I18N.tr(x.text), "strong")))))] : []),
    partyBanner(), ...specialBanners(me.special_times), ...communityBanners(me.community), ...petBanners(me.pets), today, timeLeftCard("learn")].filter(Boolean);
  if (me.profile && me.has_devices) sections.push(devicesCard());
  if (me.chores) sections.push(choresCard(me.chores));
  sections.push(subjects, deckHomeCard(), pointsCard());
  if (me.goals.length) sections.push(h("section.card", h("h2", "🎯 ", T("Goals")), ...me.goals.map(g =>
    h("div.goal", h("div.row", C(g.title, "span.grow"), h("b", g.percent ? g.value + " %" : g.value + " / " + g.target + " ★"), g.done ? "✅" : null),
      bar(g.value, g.target, g.color)))));
  if (me.family_goal) sections.push(familyGoalCard(me.family_goal));
  if (me.badges.length) sections.push(badgesCard(me.badges));
  screen("home", ...sections);
  petDiedNote(me.pets);
  dealNote(me.deals);                                   // a new offer, the deal stands … (deals.js)
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
  const unlimited = !!(st.budget && st.budget.unlimited);       // the parents set the internet budget to ∞
  const draw = () => { clock.textContent = st.running ? (unlimited ? "∞" : fmtClock(Math.max(0, left))) : unlimited ? "∞" : fmt(st.minutes) + " min"; };
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
      st.budget && !unlimited ? h("div.small.muted", "📅 ", I18N.tr(T("Budget: {0} of {1} min left")).replace("{0}", fmt(st.budget.left)).replace("{1}", fmt(st.budget.total)),
        st.extra ? " · ➕ " + fmt(st.extra) + " min" : "", " · ", I18N.tr(T("new from {0}")).replace("{0}", fmtDate(st.budget.reset_at, { weekday: "short" }) + " " + fmtTime(st.budget.reset_at))) : null),
    st.running ? h("button.btn.big.bad", { onclick: () => act("stop") }, "⏸ ", T("Pause"))
      : h("button.btn.big.good", { disabled: !st.can_start, onclick: () => act("start") }, "▶ ", T("Start")));
}

// «Me»: at the top everything about me at a glance – points, open tasks, internet time (one button: start / pause)
// and my lights; the avatar, moods and pets follow below
function meSummary() {
  const me = S.me;
  const accs = (me.accounts || []).filter(a => a.spendable);
  const open = (me.chores || []).filter(c => !c.done && !c.pending);
  const tile = (ic, value, label) => h("div.me-tile", h("span.me-ic", ic), h("b", value), h("span.small.muted", label));
  const stats = h("section.card.me-sum",
    h("div.me-tiles",
      tile("⭐", "Level " + me.level.level, fmt(me.xp_today) + " / " + fmt(me.daily_goal) + " XP " + I18N.tr(T("today"))),
      tile("🔥", String(me.streak), T("Days in a row")),
      ...[["games", "🎮", T("Games left today")], ["learn", "📚", T("Learning left today")]]
        .filter(([k]) => me.time_left && me.time_left[k] != null).map(([k, ic, label]) => tile(ic, fmtMinutes(me.time_left[k]), label)),
      ...accs.map(a => tile(a.icon || "🪙", fmt(me.balances[a.key], 1), I18N.tr(a.name))),
      tile(open.length ? "🧹" : "✅", String(open.length), open.length ? T("open tasks") : T("All done!"))),
    me.internet ? internetCard(me.internet) : null);
  return [stats, open.length ? choresCard(me.chores) : null, me.has_devices ? devicesCard() : null];
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
        c.weekly ? h("span.chore-note", T("this week")) : null,
        c.from ? h("span.chore-note.deal-note", "🤝 ", I18N.tr(T("taken over from {0}")).replace("{0}", c.from)) : null),
      c.points ? h("span.chore-pts", accIcon(c.account) + " " + fmt(c.points)) : null,
      c.energy && batteryShown() ? h("span.chore-pts.chore-energy", { title: T("Energy bonus") }, "🔋+" + c.energy) : null))) : h("p.muted", T("No chores today.")),
    open.length === 0 && chores.length ? h("p.good-text", T("All chores done – thank you!")) : null);
}

function pointsCard() {
  const me = S.me;
  const accs = me.accounts.filter(a => a.spendable);
  const nr = me.next_reward;
  return h("section.card.points", h("h2", "🪙 ", T("Points and goodies")),
    h("div.balances", ...accs.map(a => h("div.balance", h("span.bal-ic", a.icon || "🪙"), h("b", fmt(me.balances[a.key], 1)), h("span.small.muted", a.name)))),
    me.coins_reserved > 0 ? h("p.small.muted.deal-reserved", "🔒 ", I18N.tr(T("{0} coins reserved in deals")).replace("{0}", fmt(me.coins_reserved))) : null,
    me.internet ? internetCard(me.internet) : null,      // start / pause the internet time right next to the minutes
    nr ? h("div.next-reward", h("div.row", h("span.big-ic", nr.icon), h("span.grow", T("Still {0} until {1}").replace("{0}", fmt(nr.missing)).replace("{1}", nr.name))),
      bar(nr.cost - nr.missing, nr.cost)) : null,
    me.pending.length ? h("p.small.muted", "⏳ ", T("Waiting for approval:"), " ", me.pending.map(p => I18N.tr(p.name)).join(", ")) : null,
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
      h("span.pack-ic", p.icon), h("div", C(p.title, "h1"), STATUS_BADGE[p.status] ? h("span.small.status-badge", STATUS_BADGE[p.status]()) : null, " ", h("span.small", prog.percent + " % · " + prog.stars + " / " + prog.max_stars + " ★"))),
    timeLeftCard("learn"),
    h("div.row.pack-actions", { hidden: learnUp() },
      h("button.btn", { onclick: () => startLesson({ mode: "path", pack: p.id, unit: prog.next || undefined }), disabled: !prog.next }, "▶ ", T("Continue")),
      h("button.btn.ghost", { onclick: () => startLesson({ mode: "quiz", pack: p.id }), disabled: !learned }, "⚡ ", T("Quiz round")),
      p.units.some(u => u.kind === "cards") ? h("button.btn.ghost", { onclick: () => startLesson({ mode: "cards", pack: p.id }) }, "🃏 ", T("Flash cards")) : null),
    cardBox, path);
}

// ---------------------------------------------------------------- daily time (parent area › profile, timelimits.py)
const learnUp = () => !!(S.me && S.me.time_left && S.me.time_left.learn === 0);
/** «🎮 25 min left today» – at 0 a friendly stop. kind: games | learn; nothing without a limit. */
function timeLeftCard(kind) {
  const m = S.me && S.me.time_left ? S.me.time_left[kind] : null;
  if (m == null) return null;
  const up = m <= 0, ic = kind === "games" ? "🎮" : "📚";
  return h("section.card.time-left" + (up ? ".up" : ""), h("span.big-ic", up ? "🌙" : ic),
    h("strong.grow", up ? (kind === "games" ? T("Game time for today is used up – see you tomorrow!") : T("Learning time for today is used up – see you tomorrow!"))
      : I18N.tr(T("{0} left today")).replace("{0}", fmtMinutes(m))));
}

// ---------------------------------------------------------------- lesson player
async function startLesson(opts) {
  if (learnUp()) return toast(T("Learning time for today is used up – see you tomorrow!"), "bad");
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

async function quitLesson() {
  const L = S.lesson;
  if (L && L.i > 0 && L.i < L.s.steps.length && !(await confirmDialog(I18N.tr(T("Stop the lesson? What you answered so far counts."))))) return;
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
    res.streak ? h("p", "🔥 ", I18N.tr(res.streak === 1 ? T("Streak: 1 day") : T("Streak: {0} days")).replace("{0}", res.streak)) : null,
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
// a progress bar with the numbers under it («120 / 500 XP») – how far it still is
const barCount = (have, total, unit = "") => h("div.bar-count", bar(Math.min(have, total), total),
  h("span.small.muted", fmt(Math.min(have, total)) + " / " + fmt(total) + (unit ? " " + unit : "")));

async function shopView() {
  let d;
  try { d = await api("me/shop"); } catch (e) { return toast(e.message, "bad"); }
  const accs = d.accounts.filter(a => a.spendable);
  const accIcon = k => (accs.find(a => a.key === k) || {}).icon || "🪙";
  const status = { pending: T("waiting for approval"), approved: T("approved"), rejected: T("declined"), failed: T("did not work") };
  // the shop is long: chips on top (they stay while scrolling) jump to each part
  const [games, avatar, xp, pranks] = await Promise.all([unlockGamesSection(), avatarSpecials(), xpBackgrounds(), pranksCard()]);
  const wishes = d.history.length ? h("section.card", h("h2", T("My wishes")), h("ul.history", ...d.history.map(r =>
    h("li", h("span", r.icon + " "), h("span.grow", r.name), h("span.small.status." + r.status, status[r.status] || r.status))))) : null;
  const rewards = d.offers.length ? h("div.shop-grid", ...d.offers.map(o => h("div.offer.card" + (o.can ? "" : ".cant"),
      h("div.offer-ic", o.icon), h("strong", o.name),
      h("div.price", accIcon(o.account) + " " + fmt(o.cost)),
      o.approval ? h("span.small.muted", "👪 ", T("Parents confirm")) : null,
      o.can ? h("button.btn", { onclick: () => redeem(o) }, T("Redeem")) : h("div.small.muted.reason", o.reason),
      !o.can && o.missing > 0 ? barCount(o.cost - o.missing, o.cost, accIcon(o.account)) : null))) : h("p.muted", T("The shop is still empty."));
  const parts = [[rewards, "🎁", T("Rewards")], [games, "🎮", T("Unlock games")], [avatar, "🧑‍🎨", T("Avatar")], [xp, "✨", T("XP")],
    [pranks, "😈", T("Pranks")], [wishes, "📜", T("My wishes")]].filter(([el]) => el);
  parts.forEach(([el], i) => { el.id = "shop-part-" + i; el.classList.add("shop-part"); });
  const chips = parts.length > 2 ? h("nav.shop-chips", { "aria-label": T("Shop") }, ...parts.map(([el, ic, n]) =>
    h("button.chip-btn", { type: "button", onclick: () => el.scrollIntoView({ behavior: "smooth", block: "start" }) }, ic, " ", n))) : null;
  screen("shop",
    h("h1", "🛍️ ", T("Shop")),
    h("div.balances.card", ...accs.map(a => h("div.balance", h("span.bal-ic", a.icon || "🪙"), h("b", fmt(d.balances[a.key], 1)), h("span.small.muted", a.name)))),
    chips, rewards, games, avatar, xp, pranks, wishes);
  // stick right below the header (its height depends on the season scene and the screen)
  const head = document.querySelector(".fq-head, header.top");
  if (chips && head) document.documentElement.style.setProperty("--head-h", Math.round(head.getBoundingClientRect().height) + "px");
  async function redeem(o) {
    if (!(await confirmDialog(I18N.tr(T("Redeem {0} for {1}?")).replace("{0}", o.name).replace("{1}", fmt(o.cost))))) return;
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
  const items = d.items.filter(i => i.rule && i.rule.cost != null && !i.rule.off);
  if (!items.length) return null;
  const a = d.avatar;
  const wear = async i => {
    const next = { ...a, items: { ...(a.items || {}), [i.slot]: i.id } };
    try { await api("me/avatar", { method: "POST", body: { avatar: next } }); Sound.play("right"); toast(T("Your avatar wears it now"), "good"); shopView(); }
    catch (e) { toast(e.message, "bad"); }
  };
  const buy = async i => {
    if (i.rule.cost > 0 && !(await confirmDialog(I18N.tr(T("Buy {0} for {1} coins?")).replace("{0}", I18N.tr(i.name)).replace("{1}", i.rule.cost)))) return;   // price 0: free, one tap
    try { await api("me/avatar/buy", { method: "POST", body: { item: i.id } }); Sound.play("done"); confetti(); await wear(i); }
    catch (e) { toast(e.message, "bad"); }
  };
  return h("section.card", h("h2", "🧑‍🎨 ", T("Avatar specials")), h("p.small.muted", T("Only to earn: buy them with your coins and your avatar wears them.")),
    h("div.shop-grid", ...items.map(i => {
      const worn = (a.items || {})[i.slot] === i.id;
      return h("div.offer.card" + (i.unlocked || d.coins >= i.rule.cost ? "" : ".cant"),
        avatarSvg({ ...a, items: { ...(a.items || {}), [i.slot]: i.id } }, 84), h("strong", T(i.name)),
        i.unlocked ? (worn ? h("span.small.muted", "✓ ", T("You wear it")) : h("button.btn.small", { onclick: () => wear(i) }, T("Put on")))
          : [h("div.price", i.rule.cost > 0 ? "🪙 " + i.rule.cost : T("Free")), d.coins >= i.rule.cost ? h("button.btn.small", { onclick: () => buy(i) }, i.rule.cost > 0 ? T("Buy") : T("Unlock")) : barCount(d.coins, i.rule.cost, "🪙")]);
    })));
}

// backgrounds for new XP: every 500 XP earned from now on unlock one – the XP account stays as it is
async function xpBackgrounds() {
  let d;
  try { d = await api("me/avatar"); } catch { return null; }
  const items = d.items.filter(i => i.rule && i.rule.xp != null && !i.rule.off);      // price 0 = free
  if (!items.length) return null;
  const a = d.avatar, have = d.new_xp || 0;
  const wear = async i => {
    const next = { ...a, items: { ...(a.items || {}), [i.slot]: i.id } };
    try { await api("me/avatar", { method: "POST", body: { avatar: next } }); Sound.play("right"); toast(T("Your avatar wears it now"), "good"); shopView(); }
    catch (e) { toast(e.message, "bad"); }
  };
  const get = async i => {
    if (i.rule.xp > 0 && !(await confirmDialog(I18N.tr(T("Unlock {0} with {1} new XP? Your XP stay as they are.")).replace("{0}", I18N.tr(i.name)).replace("{1}", i.rule.xp)))) return;
    try { await api("me/avatar/buy", { method: "POST", body: { item: i.id } }); Sound.play("done"); confetti(); await wear(i); }
    catch (e) { toast(e.message, "bad"); }
  };
  return h("section.card", h("h2", "✨ ", T("For new XP")),
    h("p.small.muted", T("Paid with the XP you earn from now on – your XP and your level stay as they are.")),
    h("p", h("strong", "✨ " + fmt(have) + " "), T("new XP to use")),
    h("div.shop-grid", ...items.map(i => {
      const worn = (a.items || {})[i.slot] === i.id;
      return h("div.offer.card" + (i.unlocked || have >= i.rule.xp ? "" : ".cant"),
        avatarSvg({ ...a, items: { ...(a.items || {}), [i.slot]: i.id } }, 84), h("strong", T(i.name)),
        i.unlocked ? (worn ? h("span.small.muted", "✓ ", T("You wear it")) : h("button.btn.small", { onclick: () => wear(i) }, T("Put on")))
          : [h("div.price", i.rule.xp > 0 ? "✨ " + i.rule.xp + " XP" : T("Free")), have >= i.rule.xp ? h("button.btn.small", { onclick: () => get(i) }, T("Unlock")) : barCount(have, i.rule.xp, "XP")]);
    })));
}

// ---------------------------------------------------------------- pranks: the ink bomb (familyquest/pranks.py)
async function pranksCard() {
  let d;
  try { d = await api("me/pranks"); } catch { return null; }
  const buy = async () => {
    if (!(await confirmDialog(I18N.tr(T("Buy an ink bomb for {0} coins?")).replace("{0}", d.price)))) return;
    try { await api("me/pranks/buy", { method: "POST" }); Sound.play("done"); toast(T("Ink bomb bought!"), "good"); shopView(); }
    catch (e) { toast(e.message, "bad"); }
  };
  const throwIt = () => {
    const chosen = new Set();
    const go = h("button.btn.big.bad", { disabled: true, onclick: async () => {
      try {
        const r = await api("me/pranks/throw", { method: "POST", body: { targets: [...chosen] } });
        m.close(); Sound.play("wrong");
        toast(I18N.tr(T("Splash! {0} got ink")).replace("{0}", d.family.filter(p => r.hit.includes(p.id)).map(p => p.name).join(", ")), "good");
        shopView();
      } catch (e) { toast(e.message, "bad"); }
    } }, "💣 ", T("Throw!"));
    const chips = d.family.map(p => {
      const b = h("button.ink-target" + (p.hit_today ? ".off" : ""), { disabled: p.hit_today, onclick: () => {
        chosen.has(p.id) ? chosen.delete(p.id) : chosen.add(p.id);
        b.classList.toggle("on", chosen.has(p.id)); go.disabled = !chosen.size;
      } }, avatarSvg(p.avatar, 52), C(p.name, "strong"), p.hit_today ? h("span.small.muted", T("got ink today")) : null);
      return b;
    });
    const m = modal(h("div.form", h("h2", "💣 ", T("Who gets the ink bomb?")),
      h("p.small.muted", T("Choose one or more – one bomb hits all of them. Everybody can be hit once a day.")),
      h("div.ink-targets", ...chips), h("div.row", go, h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  };
  const f = d.fart;
  const buyFart = async () => {
    if (!(await confirmDialog(I18N.tr(T("Buy a whoopee cushion for {0} coins?")).replace("{0}", f.price)))) return;
    try { await api("me/pranks/buy", { method: "POST", body: { kind: "fart" } }); Sound.play("done"); toast(T("Whoopee cushion bought!"), "good"); shopView(); }
    catch (e) { toast(e.message, "bad"); }
  };
  const fart = async e => {
    const b = e.currentTarget; b.disabled = true;
    try { const r = await api("me/pranks/fart", { method: "POST" }); toast(I18N.tr(T("Pfffrrt! On {0} speakers")).replace("{0}", r.speakers), "good"); shopView(); }
    catch (err) { b.disabled = false; toast(err.message, "bad"); }
  };
  const fartCard = h("div.offer.card" + (f.left || d.coins >= f.price ? "" : ".cant"),
    h("div.offer-ic", "💨"), h("strong", T("Whoopee cushion")),
    h("span.small.muted", I18N.tr(T("A fart on all speakers of the home – {0} times per cushion.")).replace("{0}", f.uses)),
    !f.speakers ? h("span.small.warn-text", T("Needs speakers in Home Assistant")) : null,
    h("div.price", "🪙 " + f.price),
    f.left ? h("button.btn.small.bad", { disabled: !f.speakers, onclick: fart }, "💨 ", I18N.tr(T("Pfffrrt! ({0})")).replace("{0}", f.left)) : null,
    d.coins >= f.price ? h("button.btn.small" + (f.left ? ".ghost" : ""), { onclick: buyFart }, T("Buy")) : bar(d.coins, f.price));
  return h("section.card", h("h2", "😈 ", T("Pranks")),
    h("div.shop-grid", fartCard, h("div.offer.card" + (d.charges || d.coins >= d.price ? "" : ".cant"),
      h("div.offer-ic", "💣"), h("strong", T("Ink bomb")),
      h("span.small.muted", T("Smears the screen of whoever you choose with ink – they have to wipe it clean with their finger.")),
      h("div.price", "🪙 " + d.price),
      d.charges ? h("button.btn.small.bad", { onclick: throwIt }, "💣 ", I18N.tr(T("Throw ({0})")).replace("{0}", d.charges)) : null,
      d.coins >= d.price ? h("button.btn.small" + (d.charges ? ".ghost" : ""), { onclick: buy }, T("Buy")) : bar(d.coins, d.price))));
}

// the victim: ink all over the screen, wiped away with the finger; at about 85 % clean the rest fades
let inkOpen = false;
function inkOverlay(p) {
  if (inkOpen || !p) return;
  inkOpen = true;
  const cv = h("canvas.ink-canvas"), dpr = Math.min(2, window.devicePixelRatio || 1);
  const W = window.innerWidth, H = window.innerHeight;
  cv.width = W * dpr; cv.height = H * dpr;
  const g = cv.getContext("2d"); g.scale(dpr, dpr);
  // ink: a dark wash, big blobs, splashes and drips
  const rnd = (a, b) => a + Math.random() * (b - a);
  g.fillStyle = "rgba(8,8,16,.93)"; g.fillRect(0, 0, W, H);
  g.fillStyle = "#05050c";
  for (let i = 0; i < 14; i++) {
    const x = rnd(0, W), y = rnd(0, H), r = rnd(40, 130);
    g.beginPath();
    for (let k = 0; k <= 18; k++) { const a = k / 18 * Math.PI * 2, rr = r * rnd(.75, 1.25); g.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); }
    g.fill();
    for (let k = 0; k < 7; k++) { const a = rnd(0, 6.3), d = r * rnd(1.2, 2); g.beginPath(); g.arc(x + Math.cos(a) * d, y + Math.sin(a) * d, rnd(4, 14), 0, 7); g.fill(); }
  }
  for (let i = 0; i < 12; i++) { const x = rnd(0, W), y = rnd(0, H * .6), w = rnd(6, 16); g.fillRect(x, y, w, rnd(60, 220)); g.beginPath(); g.arc(x + w / 2, y + 220, w * .9, 0, 7); g.fill(); }
  g.fillStyle = "rgba(255,255,255,.07)";                                     // a little gloss
  for (let i = 0; i < 10; i++) { g.beginPath(); g.ellipse(rnd(0, W), rnd(0, H), rnd(10, 40), rnd(4, 12), rnd(0, 3), 0, 7); g.fill(); }
  const msg = h("div.ink-msg", avatarSvg(p.from.avatar, 44), h("div", h("strong", I18N.tr(T("{0} hit you with an ink bomb!")).replace("{0}", p.from.name)), h("br"), T("Wipe it clean!")));
  const box = h("div.ink-over", { role: "dialog", "aria-label": I18N.tr(T("Ink bomb")) }, cv, msg);
  document.body.append(box);
  try { Sound.play("wrong"); } catch {}
  // wiping
  g.globalCompositeOperation = "destination-out"; g.lineCap = "round"; g.lineJoin = "round"; g.lineWidth = 64;
  let last = null, done = false;
  const pos = e => [e.clientX, e.clientY];
  const wipe = e => {
    if (done) return;
    const [x, y] = pos(e);
    g.beginPath(); if (last) { g.moveTo(...last); g.lineTo(x, y); g.stroke(); } else { g.arc(x, y, 32, 0, 7); g.fill(); }
    last = [x, y]; msg.classList.add("fade");
  };
  cv.addEventListener("pointerdown", e => { cv.setPointerCapture(e.pointerId); last = null; wipe(e); });
  cv.addEventListener("pointermove", e => { if (e.buttons || e.pointerType === "touch") wipe(e); });
  cv.addEventListener("pointerup", () => { last = null; });
  // how clean? (alpha on a coarse grid)
  const check = setInterval(() => {
    const step = 12 * dpr, data = g.getImageData(0, 0, cv.width, cv.height).data;
    let n = 0, clean = 0;
    for (let y = 0; y < cv.height; y += step) for (let x = 0; x < cv.width; x += step) { n++; if (data[(Math.floor(y) * cv.width + Math.floor(x)) * 4 + 3] < 40) clean++; }
    if (clean / n < 0.85) return;
    done = true; clearInterval(check);
    box.classList.add("gone");
    api(`me/pranks/${p.id}/clean`, { method: "POST" }).then(r => { setTimeout(() => { box.remove(); inkOpen = false; toast(T("All clean!"), "good"); if (r && r.next) inkOverlay(r.next); }, 600); })
      .catch(() => { setTimeout(() => { box.remove(); inkOpen = false; }, 600); });
  }, 300);
}
setInterval(async () => {
  if (!Auth.kid || !S.me || inkOpen || document.hidden) return;
  try { const r = await api("me/pranks/pending"); if (r.prank) inkOverlay(r.prank); } catch {}
}, 5000);

// ---------------------------------------------------------------- avatar editor
async function avatarView() {
  let d;
  try { d = await api("me/avatar"); } catch (e) { return toast(e.message, "bad"); }
  const a = JSON.parse(JSON.stringify(d.avatar));
  a.items = a.items || {};
  const preview = h("div.av-preview");
  const draw = () => preview.replaceChildren(avatarSvg(a, 200));
  // names of the avatar options for screen readers (rewards/avatar.py FREE_PARTS)
  const AV_LABELS = { "hair:short": T("Short hair"), "hair:long": T("Long hair"), "hair:curly": T("Curly hair"), "hair:bun": T("Hair bun"),
    "hair:spiky": T("Spiky hair"), "hair:ponytail": T("Ponytail"), "hair:bald": T("Bald"), "eyes:round": T("Round eyes"), "eyes:happy": T("Happy eyes"),
    "eyes:wink": T("Wink"), "eyes:big": T("Big eyes"), "eyes:sad": T("Sad eyes"), "eyes:sleepy": T("Sleepy eyes"), "eyes:dizzy": T("Dizzy eyes"),
    "eyes:angry": T("Angry eyes"), "mouth:smile": T("Smile"), "mouth:grin": T("Grin"), "mouth:open": T("Open mouth"), "mouth:neutral": T("Neutral mouth"),
    "mouth:sad": T("Sad mouth"), "mouth:wavy": T("Wavy mouth"), "outfit:tshirt": T("T-shirt"), "outfit:hoodie": T("Hoodie"), "outfit:dress": T("Dress"),
    "outfit:sweater": T("Sweater"), "outfit:overall": T("Dungarees") };
  const TABS = [["skin", T("Skin")], ["hair", T("Hair")], ["hairColor", T("Hair colour")], ["eyes", T("Eyes")], ["mouth", T("Mouth")],
    ["outfit", T("Clothes")], ["outfitColor", T("Colour")], ["items", T("Items")]];
  let tab = "skin";
  const tabs = h("div.av-tabs");
  const panel = h("div.av-panel");
  const ruleText = r => r.off ? T("Not in the shop") : r.level ? T("From level {0}").replace("{0}", r.level)
    : r.badge ? T("With a badge") : r.cost != null ? (r.cost > 0 ? T("Buy for {0} coins").replace("{0}", r.cost) : T("Free"))
    : r.xp != null ? (r.xp > 0 ? I18N.tr(T("For {0} new XP")).replace("{0}", r.xp) : T("Free"))
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
      return h("button.av-opt" + (a[tab] === v ? ".on" : ""), { onclick: () => { a[tab] = v; draw(); drawPanel(); }, "aria-label": isColor ? v : I18N.tr(AV_LABELS[tab + ":" + v] || v) }, sample);
    })));
  };
  async function pickItem(i) {
    if (!i.unlocked) {
      if (i.rule.off) return toast(ruleText(i.rule));
      // price 0 (parent area › Shop): free – one tap, no question
      if (i.rule.cost != null && (i.rule.cost <= 0 || (await confirmDialog(I18N.tr(T("Buy {0} for {1} coins?")).replace("{0}", I18N.tr(i.name)).replace("{1}", i.rule.cost))))) {
        try { await api("me/avatar/buy", { method: "POST", body: { item: i.id } }); i.unlocked = true; Sound.play("done"); toast(T("Unlocked!"), "good"); }
        catch (e) { return toast(e.message, "bad"); }
      } else if (i.rule.cost == null && i.rule.xp != null && (i.rule.xp <= 0 || (await confirmDialog(I18N.tr(T("Unlock {0} with {1} new XP? Your XP stay as they are.")).replace("{0}", I18N.tr(i.name)).replace("{1}", i.rule.xp))))) {
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
  screen("avatar", h("h1", "🧑‍🎨 ", T("Me")), ...meSummary(), moods, petsSection(), h("div.av-editor", preview, h("div.av-side", tabs, panel)),
    h("div.row.center", h("button.btn.big", { onclick: save }, "💾 ", T("Save"))),
    h("div.row.center", h("button.btn.ghost", { onclick: changePin }, "🔑 ", T("Change my PIN"))),
    S.me.games ? botsSection() : null);
  async function save() {
    try { await api("me/avatar", { method: "POST", body: { avatar: a, mood_text: feel.value, mood } }); Sound.play("right"); toast(T("Saved"), "good"); go(""); }
    catch (e) { toast(e.message, "bad"); }
  }
}

// ---------------------------------------------------------------- pet care (familyquest/pets.py)
const PET_BARS = [["hunger", "🍖", T("Hunger")], ["mood", "😊", T("Mood")], ["clean", "🫧", T("Cleanliness")]];
const PET_STAGE = { egg: T("Egg"), baby: T("Baby"), young: T("Young"), adult: T("Adult") };
const petText = (t, name, x) => I18N.tr(t).replace("{0}", name).replace("{1}", x ?? "");

/** Start page: a pet that needs something (not while pet care is paused). */
function petBanners(d) {
  if (!d) return [];
  const out = [];
  for (const p of [...(d.pets || []), ...(d.sitting || [])]) {
    if (p.paused || (p.sitter && !p.owner)) continue;               // in the hotel / with a sitter: not my job now
    if (p.dying) {
      out.push(h("section.card.banner.pet-banner.sos", { onclick: () => go("avatar") }, h("span.big-ic", petIcon(p.kind, 44, p.emoji)),
        h("div.grow", C(petText(T("{0} needs you now!"), p.name), "strong"), h("br"),
          h("span.small", petText(T("All bars are empty – without care {0} leaves you in {1} days."), p.name, Math.max(0, Math.ceil(p.days_left)))))));
      continue;
    }
    const words = { hunger: T("{0} is hungry"), mood: T("{0} is bored"), clean: T("{0} needs a bath") };
    if (p.low.length) out.push(h("section.card.banner.pet-banner", { onclick: () => go("avatar") }, h("span.big-ic", petIcon(p.kind, 44, p.emoji)),
      h("div.grow", ...p.low.map(b => h("div", C(petText(words[b], p.name), "strong")))), h("span.btn.small", "🐾 ", T("Look after"))));
  }
  return out;
}

/** A pet died: a gentle message once, at the next login. */
let petDiedShown = "";
function petDiedNote(d) {
  if (!d || !d.died || !d.died.length) return;
  const key = d.died.map(p => p.id).join(",");
  if (key === petDiedShown) return;                  // the start page draws itself again – one message is enough
  petDiedShown = key;
  const m = modal(h("div.form.center.pet-died",
    h("div.pet-died-ic", "🕊️"),
    ...d.died.map(p => h("p", C(petText(T("{0} has died – take good care of your next pet"), p.name), "strong"))),
    h("p.small.muted", T("You can find a new pet in the shop.")),
    h("button.btn", { onclick: () => m.close() }, T("OK"))), { onClose: () => api("me/pets/seen", { method: "POST" }).catch(() => {}) });
}

function petsSection() {
  const sec = h("section.card.pets-sec");
  const load = async () => {
    let d; try { d = await api("me/pets"); } catch (e) { return sec.replaceChildren(h("p.bad", e.message)); }
    const head = h("div.sec-head", h("h2", "🐾 ", T("My pets")));
    const care = d.sitting && d.sitting.length ? [h("h3", "🤝 ", T("Pets in my care")),
      h("div.pet-grid", ...d.sitting.map(p => petCard(p, d.food_cost, load, d)))] : [];
    if (!d.pets.length) return sec.replaceChildren(head, h("p.muted", T("No pet yet – you can buy one in the shop.")),
      h("button.btn", { onclick: () => go("shop") }, "🛍️ ", T("To the shop")), ...care);
    const pause = d.pets[0].paused;
    sec.replaceChildren(head, ...(pause === "away" || pause === "parents" ? [h("p.pet-paused", "⏸ ", T("Holiday care"), " – ",
      h("span.small", pause === "away" ? T("you are away – your pets are looked after") : T("your parents look after your pets")))] : []),
      h("div.pet-grid", ...d.pets.map(p => petCard(p, d.food_cost, load, d))), ...care, petMoreRow(d, load));
  };
  load();
  return sec;
}

/** The pet with its outfit on (emoji or drawn degu, the outfit on top of it). */
function dressedPet(p, size) {
  if (p.stage === "egg") return h("span.pet-dressed.pet-egg", { title: I18N.tr(T("It hatches tomorrow")) }, "🥚");   // the dinosaur's egg
  const wrap = h("span.pet-dressed.kind-" + p.kind, petIcon(p.kind, size, p.emoji));
  if (p.outfit) {
    const pos = PET_WEAR_POS[p.outfit] || "body";
    wrap.append(h("span.pet-wear.pos-" + pos, petShopIcon(p.outfit, Math.round(size * { top: .5, ear: .38, eyes: .5, neck: .55, body: .62 }[pos]), true)));
  }
  return wrap;
}

/** The pet at home: the house as a backdrop, the furniture around it, the pet (element `emo`) in front. */
function petScene(p, emo) {
  const spots = ["fl", "fr", "ml", "mr", "tl", "tr"];
  return h("div.pet-home" + (p.house ? ".has-house" : ""),
    p.house ? h("div.pet-house", petShopIcon(p.house, 150)) : null,
    ...(p.furniture || []).map((f, i) => h("div.pet-furn.spot-" + spots[i % spots.length], petShopIcon(f, 36))),
    emo,
    p.happy_home ? h("span.pet-happy", "✨ ", T("Happy home")) : null);
}

/** One more pet of a kind the child has – same price as in the shop, at most 6 per kind. */
function petMoreRow(d, reload) {
  const more = (d.more || []).filter(m => m.count < m.max);
  if (!more.length) return null;
  const buy = async m => {
    if (!(await confirmDialog(I18N.tr(T("Buy one more for {0} coins?")).replace("{0}", m.price)))) return;
    try { await api("me/pets/more", { method: "POST", body: { kind: m.kind } }); Sound.play("right"); reload(); }
    catch (e) { Sound.play("wrong"); toast(e.message, "bad"); }
  };
  return h("div.pet-more-row", h("span.small.muted", T("One more of the same kind:")),
    ...more.map(m => h("button.btn.small.ghost", { onclick: () => buy(m) }, petIcon(m.kind, 20, m.emoji), " + · 🪙 ", String(m.price))));
}

/** Babies: two healthy pets of the same kind, at least 3 days old – 1 or 2 babies, then the pair rests 14 days. */
function petBreedDialog(p, d, reload) {
  const info = d.breeding[p.id] || {};
  const why = { too_young: T("at least 3 days old"), not_healthy: T("healthy – every bar at least 50"), away: T("at home"),
    resting: T("rested – they had babies not long ago") };
  const mates = d.pets.filter(x => info.partners.includes(x.id));
  const go = async mate => {
    try {
      const r = await api(`me/pets/${p.id}/breed`, { method: "POST", body: { partner: mate.id } });
      Sound.play("right"); confetti(); m.close();
      toast(I18N.tr(r.babies.length > 1 ? T("Twins! {0} babies were born") : T("A baby was born")).replace("{0}", r.babies.length), "good");
      reload();
    } catch (e) { Sound.play("wrong"); toast(e.message, "bad"); }
  };
  const m = modal(h("div.form.pet-breed",
    h("h2", "💕 ", petText(T("Babies for {0}"), p.name)),
    h("p.small.muted", T("Two healthy pets of the same kind, both at least 3 days old, can have 1 or 2 babies. Then they rest 14 days. At most 6 pets of one kind.")),
    info.why ? h("p.warn-text", petText(T("{0} must be {1} first."), p.name, I18N.tr(why[info.why]))) : null,
    !info.room ? h("p.warn-text", T("You have 6 of this kind already.")) : null,
    h("div.pet-breed-list", ...mates.map(x => {
      const ready = !info.why && info.room && (info.ready_partners || []).includes(x.id);
      const w = (d.breeding[x.id] || {}).why;
      return h("button.pet-breed-mate" + (ready ? "" : ".off"), { disabled: !ready, onclick: () => go(x) },
        dressedPet(x, 44), h("span", C(x.name, "strong"), h("br"),
          h("span.small.muted", ready ? T("ready") : w ? I18N.tr(why[w]) : "–")));
    })),
    h("div.row", h("button.btn.ghost", { onclick: () => m.close() }, T("Close")))));
}

/** Pet sitting: give the pet to a family member until a day – or to the Family Quest pet hotel for some days. */
function petSitDialog(p, d, reload) {
  const today = new Date(), iso = x => `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`;
  const inDays = n => { const x = new Date(today); x.setDate(x.getDate() + n); return iso(x); };
  const who = h("select", ...(d.family || []).map(f => h("option", { value: f.id }, f.name)));
  const until = h("input", { type: "date", value: inDays(6), min: iso(today), max: inDays(60) });
  const days = h("input", { type: "number", min: 1, max: 30, value: 7 });
  const price = h("b");
  const drawPrice = () => price.textContent = d.hotel_cost ? `🪙 ${Math.max(1, Math.min(30, +days.value || 1)) * d.hotel_cost}` : T("free");
  days.oninput = drawPrice; drawPrice();
  const run = async (path, body) => {
    try { await api(`me/pets/${p.id}/${path}`, { method: "POST", body }); Sound.play("right"); m.close(); reload(); }
    catch (e) { Sound.play("wrong"); toast(e.message, "bad"); }
  };
  const m = modal(h("div.form.pet-sit",
    h("h2", "🧳 ", petText(T("Pet sitting for {0}"), p.name)),
    h("p.small.muted", T("Away for some days, e.g. at a camp? Somebody has to look after your pet.")),
    (d.family || []).length ? h("div.card.pet-sit-opt",
      h("h3", "🤝 ", T("A family member looks after it")),
      h("p.small.muted", T("They see your pet in «Pets in my care» and feed, play and wash it – the food is on them.")),
      h("div.grid2", h("label.field", T("Who?"), who), h("label.field", T("Until (inclusive)"), until)),
      h("button.btn", { onclick: () => run("sit", { sitter: +who.value, until: until.value }) }, "🤝 ", T("Hand over"))) : null,
    h("div.card.pet-sit-opt",
      h("h3", "🏨 ", T("Family Quest pet hotel")),
      h("p.small.muted", I18N.tr(T("Your pet is looked after – no hunger, no boredom. It comes back fed, happy and clean. {0} coins per day, paid now; fetched early, full days left are paid back.")).replace("{0}", d.hotel_cost)),
      h("div.row.wrap", h("label.field", T("Days"), days), h("span.grow"), price),
      h("button.btn", { onclick: () => run("hotel", { days: +days.value }) }, "🏨 ", T("Book the pet hotel"))),
    h("div.row", h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
}

function petCard(p, cost, reload, d = {}) {
  const fetchBack = async () => {
    try { await api(`me/pets/${p.id}/fetch`, { method: "POST" }); Sound.play("right"); reload(); } catch (e) { toast(e.message, "bad"); }
  };
  if (p.hotel_until && !p.owner) return h("div.pet-card.away-card",                  // in the pet hotel
    h("div.pet-emoji", dressedPet(p, 64), h("span.pet-away-ic", "🏨")),
    C(p.name, "strong"),
    h("p.small", I18N.tr(T("In the pet hotel until {0}")).replace("{0}", fmtDate(p.hotel_until.slice(0, 10)))),
    h("button.btn.small", { onclick: fetchBack }, "🏠 ", T("Fetch early")));
  if (p.sitter && !p.owner) return h("div.pet-card.away-card",                        // with a family member
    h("div.pet-emoji", dressedPet(p, 64), h("span.pet-away-ic", "🤝")),
    C(p.name, "strong"),
    h("p.small", I18N.tr(T("{0} looks after it until {1}")).replace("{0}", p.sitter.name).replace("{1}", fmtDate(p.sit_until))),
    h("div.row.small.pet-mini-bars", ...PET_BARS.map(([k, ic]) => h("span", ic, " ", p[k]))),
    h("button.btn.small", { onclick: fetchBack }, "🏠 ", T("Take back")));
  return petCardCare(p, cost, reload, d);
}

function petCardCare(p, cost, reload, d) {
  const emo = h("div.pet-emoji", dressedPet(p, { baby: 56, young: 72, adult: 88 }[p.stage] || 72), p.stage === "baby" ? h("span.pet-bottle", "🍼") : null);
  const act = async (action, icon) => {
    try {
      await api(`me/pets/${p.id}/${action}`, { method: "POST" });
      Sound.play("right");
      emo.classList.remove("pet-hop"); void emo.offsetWidth; emo.classList.add("pet-hop");
      const fx = h("span.pet-fx", icon); emo.append(fx); setTimeout(() => fx.remove(), 1100);
      setTimeout(reload, 700);
    } catch (e) { Sound.play("wrong"); toast(e.message, "bad"); }
  };
  const rename = async () => {
    if (p.owner) return;                                             // only the owner names the pet
    const n = (await promptDialog(I18N.tr(T("New name for your pet")), p.name));
    if (n == null || !n.trim()) return;
    try { await api(`me/pets/${p.id}`, { method: "PUT", body: { name: n } }); reload(); } catch (e) { toast(e.message, "bad"); }
  };
  return h("div.pet-card.stage-" + p.stage + (p.dying ? ".dying" : ""),
    petScene(p, emo),
    p.owner ? h("div.pet-name", C(p.name, "strong")) : h("button.pet-name", { onclick: rename, title: T("Rename") }, C(p.name, "strong"), " ✏️"),
    h("div.small.muted", petText(p.age === 1 ? T("1 day old") : T("{0} days old"), p.age), " · ", I18N.tr(PET_STAGE[p.stage])),
    p.dying ? h("div.pet-sos", "🆘 ", petText(Math.ceil(p.days_left) === 1 ? T("Still 1 day – please look after {1}!") : T("Still {0} days – please look after {1}!"), Math.max(0, Math.ceil(p.days_left)), p.name)) : null,
    h("div.pet-bars", ...PET_BARS.map(([k, ic, label]) => h("div.pet-bar" + (p[k] < 25 ? ".low" : ""), { title: label },
      h("span.pet-bar-ic", ic), bar(p[k], 100, p[k] < 25 ? "var(--bad)" : p[k] < 50 ? "var(--warn)" : "var(--good)"), h("span.small", p[k])))),
    h("div.pet-actions",
      h("button.btn.small", { onclick: () => act("feed", "🍖") }, h("span.pet-act-ic", "🍖"), h("span", T("Feed")), cost ? h("span.pet-cost", "🪙 " + cost) : null),
      h("button.btn.small", { onclick: () => act("play", "❤️") }, h("span.pet-act-ic", "🎾"), h("span", T("Play"))),
      h("button.btn.small", { onclick: () => act("wash", "🫧") }, h("span.pet-act-ic", "🫧"), h("span", T("Wash")))),
    p.mining ? h("div.pet-mine" + (p.mining.on ? ".on" : ""), h("span.pet-wheel", "🎡"),
      h("span.small", p.mining.on ? I18N.tr(T("Runs in its wheel and mines {0} coins a day")).replace("{0}", p.mining.per_day)
        : T("Not healthy enough to run – every bar needs at least 50")),
      h("span.small.muted", " · ", I18N.tr(T("mined so far: {0}")).replace("{0}", p.mining.total))) : null,
    p.owner ? h("p.small.muted.pet-owner", "🤝 ", I18N.tr(T("You look after it for {0} until {1}")).replace("{0}", p.owner.name).replace("{1}", fmtDate(p.sit_until)))
      : h("div.row.wrap.pet-more",
        h("button.btn.small.ghost.pet-shop-btn", { onclick: () => petShopDialog(p, reload) }, "🛍️ ", T("Furnish & dress up")),
        h("button.btn.small.ghost", { onclick: () => petSitDialog(p, d, reload) }, "🧳 ", T("Pet sitting")),
        (d.breeding && d.breeding[p.id] && d.breeding[p.id].partners.length) ? h("button.btn.small.ghost", { onclick: () => petBreedDialog(p, d, reload) }, "💕 ", T("Babies")) : null));
}

/** Pet shop for one pet: three tabs (clothes, house, furniture) – buy, put on, move in, place. */
async function petShopDialog(p0, reload) {
  let d;
  try { d = await api("me/pets/shop"); } catch (e) { return toast(e.message, "bad"); }
  let tab = "outfit";
  const box = h("div.petshop");
  const m = modal(box, { onClose: reload });
  const pet = () => d.pets.find(x => x.id === p0.id) || { ...p0, owned: [], furniture: [] };
  const run = async (call, sound = "right") => {
    try { const r = await call(); d = r.shop; Sound.play(sound); draw(); return r; }
    catch (e) { Sound.play("wrong"); toast(e.message, "bad"); }
  };
  const buy = (it, pay) => run(() => api(`me/pets/${p0.id}/buy`, { method: "POST", body: { item: it.id, pay } }), "done")
    .then(r => { if (r) { confetti(); toast(T("Bought!"), "good"); } });
  const wear = outfit => run(() => api(`me/pets/${p0.id}/wear`, { method: "PUT", body: { outfit } }));
  const home = (house, furniture) => run(() => api(`me/pets/${p0.id}/home`, { method: "PUT", body: { house, furniture } }));
  const TABS = [["outfit", "👗", T("Clothes")], ["house", "🏠", T("House")], ["furniture", "🛋️", T("Furniture")]];
  const pays = () => d.currency === "mixed" ? ["coins", "xp"] : [d.currency];
  const priceLabel = (pay, n) => pay === "xp" ? `⭐ ${n} XP` : `🪙 ${n}`;

  function tile(it, p) {
    const own = p.owned.includes(it.id);
    let on = false, action = null;
    if (it.cat === "outfit") {
      on = p.outfit === it.id;
      if (own) action = h("button.btn.small" + (on ? ".ghost" : ""), { onclick: () => wear(on ? "" : it.id) }, on ? T("Take off") : T("Put on"));
    } else if (it.cat === "house") {
      on = p.house === it.id;
      if (own) action = h("button.btn.small" + (on ? ".ghost" : ""), { onclick: () => home(on ? null : it.id, p.furniture) }, on ? T("Move out") : T("Move in"));
    } else {
      on = p.furniture.includes(it.id);
      const full = p.furniture.length >= d.max_furniture;
      if (own) action = h("button.btn.small" + (on ? ".ghost" : ""), { disabled: !on && full,
        onclick: () => home(p.house, on ? p.furniture.filter(f => f !== it.id) : [...p.furniture, it.id]) }, on ? T("Put away") : T("Place"));
    }
    const state = on ? { outfit: T("Wears it"), house: T("Lives here"), furniture: T("Placed") }[it.cat] : own ? T("Yours") : null;
    const best = it.cat === "house" && it.best.includes(p.kind) && it.best.length < 5;
    return h("div.petshop-item" + (on ? ".on" : own ? ".own" : ""),
      petShopIcon(it.id, 52), h("strong.small", it.name),
      best ? h("span.pet-best", "★ ", T("Fits best")) : null,
      state ? h("span.small.petshop-state", "✓ ", state) : null,
      own ? action : h("div.petshop-pay", ...pays().map(pay => h("button.btn.small", { disabled: d.balance[pay] < it.price, onclick: () => buy(it, pay) },
        priceLabel(pay, it.price)))));
  }

  function draw() {
    const p = pet();
    const items = d.items.filter(i => i.cat === tab);
    const bal = pays().map(pay => priceLabel(pay, Math.floor(d.balance[pay]))).join(" · ");
    box.replaceChildren(
      h("h2", "🛍️ ", T("Furnish & dress up"), " – ", C(p.name)),
      h("div.petshop-scene", petScene(p, h("div.pet-emoji", dressedPet(p, 72)))),
      h("p.small.petshop-info", h("span", T("You have"), " ", bal), p.slow ? h("span", "😊 ", I18N.tr(T("Mood drops {0} % slower")).replace("{0}", p.slow)) : null),
      h("div.av-tabs.petshop-tabs", ...TABS.map(([k, ic, n]) => h("button" + (tab === k ? ".on" : ""), { onclick: () => { tab = k; draw(); } }, ic, " ", n))),
      h("p.small.muted", { outfit: T("A new outfit makes your pet happy (+20 mood, once)."),
        house: T("With a house the mood drops 25 % slower."),
        furniture: I18N.tr(T("Every piece of furniture: 5 % slower (at most 50 % with the house). {0} of {1} placed."))
          .replace("{0}", p.furniture.length).replace("{1}", d.max_furniture) }[tab]),
      h("div.petshop-grid", ...items.map(it => tile(it, p))),
      h("div.row.center", h("button.btn", { onclick: () => m.close() }, T("Close"))));
  }
  draw();
}

// ---------------------------------------------------------------- own bots for the games (shared with the family or not)
const BOT_COLORS = ["#5b5bd6", "#d6336c", "#e8590c", "#0c8599", "#2f9e44", "#7048e8", "#f59f00", "#495057"];
const BOT_LEVELS = { easy: T("easy"), normal: T("normal"), hard: T("hard") };
function botBadge(b, size = 52) {
  return h("span.bot-av", { style: { width: size + "px", height: size + "px", fontSize: (size * .58) + "px", background: b.color || "var(--hover)" } },
    ["degu", "goldfish"].includes(b.kind) ? petIcon(b.kind, size * .72) : b.emoji || "🤖");
}
function botsSection() {
  const sec = h("section.card.bots-sec");
  const load = async () => {
    let d; try { d = await api("community/bots"); } catch (e) { return sec.replaceChildren(h("p.bad", e.message)); }
    sec.replaceChildren(h("div.sec-head", h("h2", "🤖 ", T("My bots")), h("div.head-actions", h("button.btn", { onclick: () => botDialog(null, d.emojis, load) }, "+ ", T("New bot")))),
      h("p.small.muted", T("Make your own bots – they play with you in Tschau Sepp, Kartenkarussell and Texas Hold'em. Shared bots can play with your siblings too.")),
      d.bots.filter(b => !b.pet).length ? h("div.bot-grid", ...d.bots.filter(b => !b.pet).map(b => h("button.bot-tile", { onclick: () => b.mine ? botDialog(b, d.emojis, load) : toast(I18N.tr(T("A bot of {0}")).replace("{0}", b.owner || "?")) },
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
      b ? h("button.btn.small.bad", { onclick: async () => { if (!(await confirmDialog(I18N.tr(T("Delete the bot «{0}»?")).replace("{0}", b.name)))) return;
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
    ear: T("Ears"), neck: T("Neck"), suit: T("Costumes"), figure: T("Figure"), back: T("On the back"), hand: T("In the hand"), pet: T("Pets") }[s] || s;
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
    await familyTimeSection(), await councilSection(), await pollsSection(), await boardsSection(),
    S.me.stories !== false ? storiesCard() : null, await wichtelnSection(), await historySection());
}

// ---------------------------------------------------------------- games with a price: buy or rent (familyquest/gamepasses.py)
const GAME_INFO = { quiz: ["🎯", T("Family quiz")], bingo: ["🎱", "Bingo"], song: ["🎵", T("Guess the song")], poker: ["🃏", "Texas Hold'em"],
  tschau: ["🂡", "Tschau Sepp"], karussell: ["🎠", T("Card Carousel")], domino: ["🁫", "Domino"], paarjagd: ["🧠", T("Pair Hunt")], werbinich: ["🎭", T("Who am I?")],
  kartenlauf: ["🏁", T("Card Race")], stadtland: ["🏙️", T("City, Country, River")], zeichnen: ["🎨", T("Draw & Guess")], wuerfel: ["🎲", T("Five Dice")],
  heimwaerts: ["🏠", T("Homeward")], jump: ["🦘", "Jump"], sternlauf: ["🌠", T("Star Runner")], snack: ["🍔", T("Snack Rush")], verkehr: ["🚦", T("Traffic Cadet")],
  klatsch: ["👏", T("Clap the Beat")], verboten: ["🚫", T("Forbidden Words")], jass: ["♣️", T("Jass")], werwolf: ["🐺", T("Werewolves")], schach: ["♟️", T("Chess")],
  dorfmarkt: ["🏘️", T("Village Market")], escape: ["🗝️", T("Escape Room")], stempeljagd: ["🏛️", T("Beat the Bureaucracy")], ttt: ["⭕", T("Tic-Tac-Toe")], sudoku: ["🔢", T("Sudoku")], patience: ["🃏", T("Patience")],
  pingpong: ["🏓", T("Ping-Pong")], slots: ["🎰", T("One-armed bandit")], cube: ["🧊", T("Cube solver")] };
GAME_INFO.langstrecke = ["🏎️", T("24h Endurance")];
GAME_INFO.adventuregame = ["🗝️", T("Adventure games")];
const gameInfo = k => GAME_INFO[k] || ["🎮", k];
const rentText = o => I18N.tr({ day: T("Rent: {0} 🪙 per day"), week: T("Rent: {0} 🪙 per week"), month: T("Rent: {0} 🪙 per month") }[o.period] || T("Rent: {0} 🪙 per week")).replace("{0}", o.rent);
const buyText = o => I18N.tr(T("Buy: {0} 🪙")).replace("{0}", o.price);
function passStatus(o) {
  if (o.bought) return I18N.tr(T("bought ✓"));
  if (!o.rent_until) return "";
  const d = Math.ceil(o.left_s / 86400), hr = Math.ceil(o.left_s / 3600);
  return o.left_s <= 23 * 3600 ? I18N.tr(hr === 1 ? T("rented – 1 hour left") : T("rented – {0} hours left")).replace("{0}", hr)
    : I18N.tr(d === 1 ? T("rented – 1 day left") : T("rented – {0} days left")).replace("{0}", d);
}
// buy or rent after a confirmation – the coins are booked on the server (once: a second tap books nothing)
async function gamePass(o, kind, after) {
  const name = I18N.tr(gameInfo(o.game)[1]);
  const q = kind === "buy" ? I18N.tr(T("Buy {0} for {1} coins? It stays yours for good.")).replace("{0}", name).replace("{1}", o.price)
    : I18N.tr(o.rent_until ? T("Rent {0} for {1} coins more? The time is added to the end.") : T("Rent {0} for {1} coins?")).replace("{0}", name).replace("{1}", o.rent);
  if (!(await confirmDialog(q))) return;
  try {
    await api("me/games/buy", { method: "POST", body: { game: o.game, kind, until: kind === "rent" ? (o.rent_until || "") : null } });
    Sound.play("done"); confetti(); toast(kind === "buy" ? T("Game unlocked – have fun!") : T("Game rented – have fun!"), "good");
  } catch (e) { toast(e.message, "bad"); }
  try { S.me = await api("me"); } catch {}
  if (after) after();
}
function gamePassButtons(o, coins, after) {
  const btn = (kind, cost, text) => coins >= cost ? h("button.btn.small", { onclick: () => gamePass(o, kind, after) }, text)
    : h("button.btn.small.ghost", { disabled: true, title: T("Not enough coins") }, text);
  return h("div.row.wrap.gp-buttons", o.price > 0 && !o.bought ? btn("buy", o.price, buyText(o)) : null,
    o.rent > 0 && !o.bought ? btn("rent", o.rent, rentText(o)) : null);
}
const cheapest = o => Math.min(...[o.price, o.rent].filter(x => x > 0));
// a locked tile (games page, game corner): what it costs and the buttons in a sheet
// `card`: the game's card (family games) – a free try opens it; starting or joining a table there uses the try
async function gamePassDialog(o, card) {
  let coins = 0;
  try { const d = await api("me/games/shop"); coins = d.coins; o = d.games.find(g => g.game === o.game) || o; } catch {}
  const [ic, name] = gameInfo(o.game);
  if (S.sheet) S.sheet.close();
  const arcade = typeof ARCADE !== "undefined" && !!ARCADE[o.game];
  const tryIt = async () => {
    if (arcade) {             // the game corner: the try (and a battery segment) is used when the game opens (minigames.js arcadeView)
      S.trial = o.game; m.close(); go("arcade/" + o.game);
    } else if (card) { m.close(); openGameSheet(card); }
  };
  const canTry = o.tries_left > 0 && (arcade || card);
  const m = modal(h("div.game-sheet.gp-sheet", h("section.card", h("h2", ic, " ", I18N.tr(name), " 🔒"),
      h("p", T("Your parents put a price on this game. Buy it once and it stays yours – or rent it for a while.")),
      canTry ? [h("p.gp-try", "🎁 ", triesText(o.tries_left), " – ", T("try it before you buy or rent it.")),
        arcade ? null : h("p.small.muted", T("Starting or joining a table uses a free try. Once you sit at the table you can play it to the end.")),
        h("button.btn.big.gp-try-btn", { onclick: tryIt }, "🎁 ", T("Try for free"))] : null,
      h("p.small.muted", "🪙 ", I18N.tr(T("You have {0} coins")).replace("{0}", Math.floor(coins))),
      gamePassButtons(o, coins, () => { m.close(); route(); }), coins < cheapest(o) ? barCount(coins, cheapest(o), "🪙") : null),
    h("button.btn.ghost.small", { onclick: () => m.close() }, T("Close"))), { onClose: () => { if (S.sheet === m) S.sheet = null; } });
  S.sheet = m;
}
// kid shop: «🎮 Unlock games» – every game with a price this child may play
async function unlockGamesSection() {
  let d;
  try { d = await api("me/games/shop"); } catch { return null; }
  if (!d.games.length) return null;
  return h("section.card.gp-shop", h("h2", "🎮 ", T("Unlock games")),
    h("p.small.muted", T("Buy a game once and it stays yours – or rent it for a while.")),
    h("div.gp-list", ...d.games.map(o => {
      const [ic, name] = gameInfo(o.game);
      return h("div.gp-item" + (o.open ? ".open" : ""), h("span.big-ic", ic),
        h("div.grow", h("strong", I18N.tr(name)), o.open ? h("div.small.gp-status", passStatus(o))
          : o.tries_left > 0 ? h("div.small.gp-status", "🎁 ", triesText(o.tries_left)) : null),
        o.bought ? null : gamePassButtons(o, d.coins, () => shopView()));
    })));
}

// ---------------------------------------------------------------- the games (own menu item)
async function gamesView() {
  S.trial = null;             // a game of the game corner opened on a free try: locked again once closed
  const quiz = canPlay("quiz") || tableOnly("quiz") || (trialGame("quiz") && trialGame("quiz").member) ? await quizCard() : null;
  // longer table games for a game night, then short games for in between (only the games this child may play) –
  // each one a small tile; a tap opens its card (the same actions as before: family table, bots, join, rules);
  // a game with a price not bought yet: a 🔒 tile that opens buying / renting; locked, but a parent's table is open: its card
  // locked with free tries left: the 🔒 tile also offers the try (its card); seated at a table on a try: the normal tile
  const pick = async list => (await Promise.all(list.map(async ([k, ok, make]) => ok || tableOnly(k) || (trialGame(k) && trialGame(k).member) ? [k, await make()]
    : lockedGame(k) ? [k, trialGame(k) ? await make() : null, lockedGame(k)] : null))).filter(x => x && (x[1] || x[2]));
  const night = await pick([["tschau", canPlay("tschau"), () => cardsFamilyCard("tschau")], ["karussell", canPlay("karussell"), () => cardsFamilyCard("karussell")], ["domino", canPlay("domino"), dominoFamilyCard],
    ["jass", canPlay("jass"), jassFamilyCard], ["poker", canPlay("poker"), pokerFamilyCard], ["dorfmarkt", canPlay("dorfmarkt"), dorfmarktFamilyCard], ["heimwaerts", canPlay("heimwaerts"), heimwaertsFamilyCard],
    ["langstrecke", canPlay("langstrecke"), langstreckeFamilyCard],
    ["kartenlauf", canPlay("kartenlauf"), kartenlaufFamilyCard], ["werwolf", canPlay("werwolf"), werwolfFamilyCard], ["escape", canPlay("escape"), escapeFamilyCard], ["stempeljagd", canPlay("stempeljagd"), stempeljagdFamilyCard], ["werbinich", canPlay("werbinich"), werbinichFamilyCard],
    ["verboten", canPlay("verboten"), verbotenFamilyCard], ["zeichnen", canPlay("zeichnen"), zeichnenFamilyCard], ["stadtland", canPlay("stadtland"), stadtlandFamilyCard], ["song", canPlay("song"), songFamilyCard],
    ["bingo", canPlay("bingo"), bingoCard], ["schach", canPlay("schach"), schachFamilyCard]]);
  if (!quiz && lockedGame("quiz")) night.unshift(["quiz", trialGame("quiz") ? await quizCard() : null, lockedGame("quiz")]);
  const quick = await pick([["paarjagd", canPlay("paarjagd"), paarjagdFamilyCard], ["wuerfel", canPlay("wuerfel"), wuerfelFamilyCard], ["jump", canPlay("jump"), jumpFamilyCard], ["klatsch", canPlay("klatsch"), klatschFamilyCard],
    ["sternlauf", canPlay("sternlauf"), sternlaufFamilyCard], ["snack", canPlay("snack"), snackFamilyCard], ["verkehr", canPlay("verkehr"), verkehrFamilyCard], ["duel", canPlay("ttt") || canPlay("pingpong"), tttDuelCard]]);
  // the games running just now on top – the same pulsing banners as on the start page
  const live = communityBanners(S.me && S.me.community, { gamesOnly: true });
  screen("games", h("div.row.games-head", h("h1.grow", "🎲 ", T("Games")), batteryShown() ? h("button.bat-chip", { onclick: () => battery().free || battery().charge >= battery().cap ? null : rechargeBattery(),
      title: T("Game battery") }, batteryIcon(battery())) : null),
    partyBanner(), batteryShown() && batteryEmpty() ? h("section.card.bat-card", batteryBar()) : null, timeLeftCard("games"), ...(live.length ? [h("div.live-banners", ...live)] : []), quiz,
    // the adventure games of the family (stories.js): switched on for this child and the library open for it
    canPlay("adventuregame") && S.me.stories !== false ? adventureGamesCard() : null,
    gameGroup("🎲", T("For a game night"), night), gameGroup("⚡", T("Quick games for in between"), quick), arcadeCard());
}

/** A group of family games as small tiles (icon + name, a pulsing dot while a table runs); a tap opens the game's card. */
function gameGroup(ic, title, items) {
  if (!items.length) return null;
  const com = (S.me && S.me.community) || {};
  return h("section.card.game-group", h("h2", ic, " ", title),
    h("div.arcade-grid.game-tiles", ...items.map(([k, card, lock]) => {
      if (lock) return lockedTile(k, lock, card);
      const head = card.querySelector("h2");
      const text = (head ? head.textContent : k).trim(), sp = text.indexOf(" ");
      const icon = sp > 0 ? text.slice(0, sp) : "🎲", name = sp > 0 ? text.slice(sp + 1) : text;
      const running = k === "duel" ? com.duel || com.pong4 : com[k];
      return h("button.arcade-tile.game-tile" + (running ? ".live" : ""), { onclick: () => openGameSheet(card) },
        running ? h("i.live-dot", { title: T("running now") }) : null, h("span.big-ic", icon), h("strong", name));
    })));
}

/** A tile of a game with a price not bought yet: 🔒 and the price – a tap opens buying / renting. */
function lockedTile(k, o, card) {
  const [ic, name] = gameInfo(k);
  return h("button.arcade-tile.game-tile.gp-locked", { onclick: () => gamePassDialog(o, card), title: T("Unlock games") },
    h("span.big-ic", ic), h("strong", I18N.tr(name)),
    h("span.gp-price", h("span", "🔒 ", (o.price > 0 ? o.price : o.rent) + " 🪙"),
      o.price > 0 ? null : h("span", "/" + I18N.tr({ day: T("Day"), week: T("Week"), month: T("Month") }[o.period] || T("Week")))),
    o.tries_left > 0 ? h("span.gp-try-tag", "🎁 ", triesText(o.tries_left)) : null);
}

// the card of a game in a sheet: closes itself when the app goes to another page (a game opened, a table joined)
function openGameSheet(card) {
  if (S.sheet) S.sheet.close();
  card.classList.add("in-sheet");
  const m = modal(h("div.game-sheet", batteryHint(), card, h("button.btn.ghost.small", { onclick: () => m.close() }, T("Close"))),
    { onClose: () => { window.removeEventListener("hashchange", off); if (S.sheet === m) S.sheet = null; } });
  const off = () => m.close();
  window.addEventListener("hashchange", off);
  S.sheet = m;
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
const LANG_NAMES = { de: T("German"), en: T("English"), fr: T("French"), it: T("Italian"), es: T("Spanish"), nl: T("Dutch"), pl: T("Polish"), pt: T("Portuguese"), sv: T("Swedish") };
// the course description in the app language (packs may carry beschreibung_i18n), else in the language of the pack
function courseText(c) {
  const d = c.descriptions || {}, l = I18N.lang, b = String(I18N.base || l).split("-")[0];
  return d[l] || d[b] || (b !== (c.src_lang || "de") && b !== "de" && d.en) || c.description;
}

async function coursesView() {
  let list = [];
  try { list = await api("me/courses"); } catch (e) { return toast(e.message, "bad"); }
  const LEVELS = { A1: T("Beginner"), A2: T("Basics"), B1: T("Advanced") };
  const levelName = l => l === "für alle" ? I18N.tr(T("for everybody")) : l;       // the level of the general knowledge pack
  const groups = new Map();
  for (const c of list) { const k = c.subject.key; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(c); }
  const toggle = async (c, on) => {
    try { await api(`me/courses/${encodeURIComponent(c.id)}`, { method: "POST", body: { on } }); }
    catch (e) { return toast(e.message, "bad"); }
    if (on) { Sound.play("done"); go("pack/" + encodeURIComponent(c.id)); } else coursesView();
  };
  try { S.me = await api("me"); } catch {}
  const me = S.me, isParent = me.profile && me.profile.role === "parent";
  screen("courses", { back: () => go("") },
    h("h1", "📚 ", T("Learning")),
    h("section.card.learn-start",
      h("div.grow", h("strong", T("Daily lesson")), h("div.small.muted", T("A short lesson mixes repetitions and new words."))),
      h("button.btn.big", { onclick: () => startLesson({ mode: "daily" }) }, "▶ ", T("Start"))),
    me.codelab ? codelabTile() : null,                    // 💡 Code Workshop (codelab.js) – only in the dev channel
    h("section", h("h2", T("Subjects")),
      isParent ? h("p.small.muted", "👀 ", T("As a parent you see all packs to try them out – also drafts. Children only see the packs switched on for them.")) : null,
      subjectGrid(me, true)),
    h("h2", "🌍 ", T("Language courses & more")),
    h("p.muted", T("Choose a language and your level – the units unlock one after the other. Everybody can learn: children and adults.")),
    list.length ? [...groups.values()].map(cs => h("section.card.course", { style: { "--c": cs[0].subject.color } },
      h("h2", cs[0].subject.icon + " ", I18N.tr(cs[0].subject.name)),
      h("div.course-levels", ...cs.sort((a, b) => String(a.level).localeCompare(String(b.level)) || String(a.title).localeCompare(String(b.title))).map(c => h("div.course-level" + (c.on ? ".on" : ""),
        h("strong", { translate: "no" }, levelName(c.level)), LEVELS[c.level] ? h("span.small", I18N.tr(LEVELS[c.level])) : null,
        // two packs of one subject with the same level («für alle»): the pack title tells them apart
        cs.filter(x => x.level === c.level).length > 1 ? h("b.course-title", { translate: "no" }, c.title) : null,
        C(courseText(c) || c.title, "span.small.muted"),
        // a pack written in one language only (e.g. German general knowledge) says so in other app languages
        (c.content_langs || []).length && !c.content_langs.includes(String(I18N.base || I18N.lang).split("-")[0])
          ? h("span.small.muted", I18N.tr(T("Content in {0}")).replace("{0}", c.content_langs.map(l => I18N.tr(LANG_NAMES[l] || l)).join(", "))) : null,
        h("span.small.muted", c.units + " " + I18N.tr(T("units")) + " · " + c.cards + " " + I18N.tr(T("cards"))),
        c.on ? h("div.row", h("button.btn.small", { onclick: () => go("pack/" + encodeURIComponent(c.id)) }, "▶ ", T("Continue")),
                 h("button.btn.small.ghost", { onclick: () => toggle(c, false) }, T("Remove")))
             : h("button.btn.small", { onclick: () => toggle(c, true) }, "+ ", T("Start")))))))
      : h("p.muted", T("No courses yet.")));
}

boot();
