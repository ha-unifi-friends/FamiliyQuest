// Guest page: friends and grandparents scan the QR code of a running family game, type a name and play along.
// Only the games are open to them – the guest token is not a family login. It stays on this device for the visit
// (24 hours, familyquest/guests.py): the lobby lists the family tables open to join – one tap, no new QR code.
"use strict";
const app = document.getElementById("app");
const CODE = new URLSearchParams(location.search).get("c") || "";
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch {} },
};
// the shared game views ask Auth.kid for the token: here it is the guest token of this device
Object.defineProperty(Auth, "kid", { get() { return store.get("fq.guest") || ""; }, set(v) { store.set("fq.guest", v || null); } });
Object.defineProperty(Auth, "parent", { get: () => "", set() {} });
const screen = (...xs) => app.replaceChildren(h("main.guest-main", ...xs.flat().filter(Boolean)));
let me = null;
try { me = JSON.parse(store.get("fq.guest.me") || "null"); } catch {}
const saveMe = p => { me = p; store.set("fq.guest.me", p ? JSON.stringify(p) : null); };
let lobbyTimer = null;           // the lobby polls for new tables (like the table note of the app, kid.js)
const GAME_ICONS = { quiz: "🎯", bingo: "🎱", poker: "🃏", tschau: "🂡", karussell: "🎠", song: "🎵", domino: "🁫", paarjagd: "🧠", werbinich: "🎭", kartenlauf: "🏁", stadtland: "🏙️", zeichnen: "🎨", wuerfel: "🎲", heimwaerts: "🏠", jump: "🦘", sternlauf: "🌠", snack: "🍔", verkehr: "🚦", langstrecke: "🏎️", klatsch: "👏", verboten: "🚫", jass: "♣️", werwolf: "🐺", schach: "♟️", dorfmarkt: "🏘️", escape: "🗝️", stempeljagd: "🏛️" };
const GAME_TITLES = { bingo: "Bingo", poker: "Texas Hold'em", tschau: "Tschau Sepp", karussell: T("Card Carousel"), song: T("Guess the song"), domino: "Domino", paarjagd: T("Pair Hunt"), werbinich: T("Who am I?"), kartenlauf: T("Card Race"), stadtland: T("City, Country, River"), zeichnen: T("Draw & Guess"), wuerfel: T("Five Dice"), heimwaerts: T("Homeward"), jump: "Jump", sternlauf: T("Star Runner"), snack: T("Snack Rush"), verkehr: T("Traffic Cadet"), langstrecke: T("24h Endurance"), klatsch: T("Clap the Beat"), verboten: T("Forbidden Words"), jass: T("Jass"), werwolf: T("Werewolves"), schach: T("Chess"), dorfmarkt: T("Village Market"), escape: T("Escape Room"), stempeljagd: T("Beat the Bureaucracy") };
let catalog = null;           // the free avatar parts and items for guests (guest/info: rewards/avatar.py guest_catalog)

// quick picks for the avatar: clearly female and clearly male looks, different skin and hair – free parts only
const GUEST_LOOKS = [
  [T("Woman"), { skin: "#ffe0bd", hair: "long", hairColor: "#b5651d", eyes: "happy", mouth: "smile", outfit: "dress", outfitColor: "#f783ac", items: { hairclip: "clip_bow" } }],
  [T("Woman"), { skin: "#8d5524", hair: "ponytail", hairColor: "#111111", eyes: "round", mouth: "grin", outfit: "dress", outfitColor: "#845ef7", items: {} }],
  [T("Grandma"), { skin: "#f1c27d", hair: "bun", hairColor: "#9aa0a6", eyes: "happy", mouth: "smile", outfit: "sweater", outfitColor: "#20c997", items: { eyewear: "glasses" } }],
  [T("Man"), { skin: "#c68642", hair: "short", hairColor: "#2b1b0e", eyes: "round", mouth: "smile", outfit: "hoodie", outfitColor: "#4f8cff", items: {} }],
  [T("Man"), { skin: "#ffe0bd", hair: "spiky", hairColor: "#e6be8a", eyes: "happy", mouth: "grin", outfit: "tshirt", outfitColor: "#51cf66", items: {} }],
  [T("Grandpa"), { skin: "#e0ac69", hair: "bald", hairColor: "#9aa0a6", eyes: "round", mouth: "smile", outfit: "sweater", outfitColor: "#495057", items: { eyewear: "glasses_square" } }],
  [T("Person"), { skin: "#5c3a21", hair: "curly", hairColor: "#111111", eyes: "happy", mouth: "smile", outfit: "overall", outfitColor: "#fcc419", items: {} }],
  [T("Person"), { skin: "#f1c27d", hair: "short", hairColor: "#d94f2b", eyes: "wink", mouth: "grin", outfit: "tshirt", outfitColor: "#ff922b", items: {} }],
];
const copyAv = a => JSON.parse(JSON.stringify(a));

// «✏️ Customize»: the avatar builder of the parent area (shared/avatar.js avatarEditorBox) with the free parts only
function customizeAvatar(start) {
  return new Promise(resolve => {
    const a = copyAv(start || GUEST_LOOKS[0][1]);
    const m = modal(h("div.form", h("h2", "✏️ ", T("Customize")), avatarEditorBox(catalog || { parts: {}, slots: [], items: [] }, a),
      h("div.row", h("button.btn", { type: "button", onclick: () => { resolve(a); m.close(); } }, "✓ ", T("Done")),
        h("button.btn.ghost", { type: "button", onclick: () => m.close() }, T("Cancel")))), { onClose: () => resolve(null), wide: true });
  });
}

// the row of quick picks + «🎲 Random» + «✏️ Customize»; value() → the chosen avatar (null: a random one by the server)
function avatarPicker(current = null, { random = true } = {}) {
  let chosen = current ? copyAv(current) : (random ? null : copyAv(GUEST_LOOKS[0][1]));
  let custom = null;                                     // a look made with «Customize»
  const row = h("div.guest-avs", { role: "group", "aria-label": I18N.tr(T("Your avatar")) });
  const same = (x, y) => !!x && !!y && JSON.stringify(x) === JSON.stringify(y);
  if (chosen && !GUEST_LOOKS.some(([, l]) => same(l, chosen))) custom = chosen;
  const draw = () => row.replaceChildren(
    ...GUEST_LOOKS.map(([label, look]) => h("button.guest-av" + (same(look, chosen) ? ".on" : ""), { type: "button", title: label, "aria-label": label,
      "aria-pressed": String(same(look, chosen)), onclick: () => { chosen = copyAv(look); draw(); } }, avatarSvg(look, 52))),
    custom ? h("button.guest-av" + (same(custom, chosen) ? ".on" : ""), { type: "button", title: I18N.tr(T("My avatar")), "aria-label": I18N.tr(T("My avatar")),
      "aria-pressed": String(same(custom, chosen)), onclick: () => { chosen = copyAv(custom); draw(); } }, avatarSvg(custom, 52)) : null,
    random ? h("button.btn.small.ghost.guest-av-btn" + (chosen ? "" : ".on"), { type: "button", "aria-pressed": String(!chosen),
      onclick: () => { chosen = null; draw(); } }, "🎲 ", T("Random")) : null,
    h("button.btn.small.ghost.guest-av-btn", { type: "button", onclick: async () => {
      const a = await customizeAvatar(chosen || custom);
      if (a) { custom = a; chosen = copyAv(a); draw(); }
    } }, "✏️ ", T("Customize")));
  draw();
  return { el: row, value: () => (chosen ? copyAv(chosen) : null) };
}

// ☰ › «My avatar» in the running game (shared/ui.js openGameMenu): change it – the seat at the table follows
function myAvatarDialog(game) {
  const pick = avatarPicker(me && me.avatar, { random: false });
  const m = modal(h("div.form.center", h("h2", "🧑‍🎨 ", T("My avatar")), pick.el,
    h("div.row.center", h("button.btn", { type: "button", onclick: async () => {
      try {
        const r = await api("guest/avatar", { method: "PUT", body: { avatar: pick.value() } });
        saveMe({ ...me, avatar: r.avatar });
        m.close(); toast(T("Saved"), "good"); game ? play(me, game) : lobby();     // draw the table anew with the new seat
      } catch (e) { toast(e.message, "bad"); }
    } }, "💾 ", T("Save")), h("button.btn.ghost", { type: "button", onclick: () => m.close() }, T("Cancel")))));
}

const invalid = () => screen(h("section.card.center", h("div.big-ic", "🎲"), h("h2", T("This invitation is not valid (any more)")),
  h("p.muted", T("Ask the family for a new QR code.")), h("div.row.center", langPicker())));

// the guest profile of this device: still valid? (null: expired, deleted or none)
async function loadLobby() {
  if (!Auth.kid) return null;
  try {
    const l = await api("guest/lobby" + (catalog ? "" : "?catalog=1"));      // the free avatar parts once (☰ › My avatar)
    if (l.avatar_catalog) catalog = l.avatar_catalog;
    return l;
  }
  catch (e) {
    if (e.status === 401 || e.status === 403) { Auth.kid = ""; saveMe(null); }
    if (e.status === 401 || e.status === 403 || !me) return null;
    return { on: true, tables: [], profile: me, offline: true };          // a network hiccup: keep the guest
  }
}

async function start() {
  let info = null;
  if (CODE) { try { info = await api("community/guest/info?code=" + encodeURIComponent(CODE)); } catch {} }
  if (info) catalog = info.avatar_catalog || null;
  const l = await loadLobby();
  if (l) {
    saveMe({ ...me, ...l.profile });
    if (info) {                                       // a new invitation with a guest profile: straight to that table
      const t = l.tables.find(x => x.game === info.game);
      if (t) return enter(t);
    }
    return lobby(l);
  }
  if (!info) return invalid();
  const look = avatarPicker();
  const name = h("input", { type: "text", maxlength: 20, autocomplete: "nickname", placeholder: I18N.tr(T("Your name")) });
  const go = async () => {
    if (!name.value.trim()) return name.focus();
    try {
      const r = await api("community/guest/join", { method: "POST", body: { code: CODE, name: name.value, avatar: look.value() } });
      Auth.kid = r.token; saveMe(r.profile);
      history.replaceState(null, "", location.pathname);               // the code is used: a reload opens the lobby
      play(me, r.game);
    } catch (e) { toast(e.message, "bad"); }
  };
  name.addEventListener("keydown", e => { if (e.key === "Enter") go(); });
  screen(h("section.card.center.guest-join",
    h("img", { src: "img/icon.svg", alt: "", width: 64, height: 64 }),
    h("h1", info.game === "quiz" ? ["🎯 ", C(info.title)] : (GAME_ICONS[info.game] || "🎯") + " " + I18N.tr(GAME_TITLES[info.game] || "")),
    h("p", T("You are invited to play along! What is your name?")),
    name, h("p.small.muted.guest-av-q", T("Pick your avatar:")), look.el, h("button.btn.big", { onclick: go }, "🙋 ", T("Join")),
    h("div.row.center", langPicker())));
  name.focus();
}

// «Join» in the lobby: sit down at that table (the guest token is the permission) and play
async function enter(t) {
  clearTimeout(lobbyTimer);
  if (!t.joined) {
    try { await api(t.join, { method: "POST" }); }
    catch (e) { toast(e.message, "bad"); return lobby(); }
  }
  play(me, t.game);
}

// the lobby: the family tables open to join just now – polled, so a new table appears by itself
async function lobby(first) {
  clearTimeout(lobbyTimer);
  window.FQ_GUEST_AVATAR = () => myAvatarDialog(null);
  const list = h("div.guest-tables", { "aria-live": "polite" });
  const note = h("p.small.muted.center");
  let lastSig = "";
  const draw = l => {
    const sig = JSON.stringify([l.on, l.tables]);
    if (sig === lastSig) return;
    lastSig = sig;
    note.textContent = l.on ? I18N.tr(T("New tables appear here by themselves.")) : I18N.tr(T("Guests are switched off right now."));
    list.replaceChildren(...(l.tables.length ? l.tables.map(t => h("div.guest-table" + (t.joined ? ".mine" : ""),
      h("span.guest-table-ic", { "aria-hidden": "true" }, t.icon || GAME_ICONS[t.game] || "🎲"),
      h("div.grow", h("strong", t.game === "quiz" ? C(t.title) : I18N.tr(t.title)),
        h("div.small.muted", C(t.host || "?"), " · ", I18N.tr(T("Players: {0}")).replace("{0}", t.players),
          t.status === "lobby" ? "" : " · " + I18N.tr(T("Running")))),
      h("button.btn" + (t.joined ? ".ghost" : ""), { onclick: () => enter(t) }, t.joined ? T("Back to the game") : ["▶ ", T("Join")])))
      : [h("div.guest-empty.center", h("div.big-ic", "🕰️"), h("p", T("No table is open right now.")),
        h("p.small.muted", T("As soon as somebody of the family opens a table, it appears here."))) ]));
  };
  const leave = async () => {
    if (!await confirmDialog(T("Leave and delete your guest profile? To play again you need a new QR code."), { ok: T("Leave"), danger: true })) return;
    try { await api("guest/me", { method: "DELETE" }); } catch {}
    clearTimeout(lobbyTimer); Auth.kid = ""; saveMe(null);
    screen(h("section.card.center", h("div.big-ic", "👋"), h("h2", T("Thanks for playing!")), h("p.muted", T("Your guest profile is deleted."))));
  };
  screen(h("section.card.guest-lobby",
    h("div.row.guest-me", me ? avatarSvg(me.avatar || {}, 56) : null,
      h("div.grow", h("div.small.muted", T("Guest")), h("h1", C(me ? me.name : ""))),
      h("button.btn.small.ghost", { title: T("My avatar"), onclick: () => myAvatarDialog(null) }, "🧑‍🎨")),
    h("h2", "🎲 ", T("Open tables")), list, note),
    h("div.row.center.wrap.guest-foot", langPicker(), h("button.btn.small.ghost.bad", { onclick: leave }, "🚪 ", T("Leave"))));
  const poll = async l => {
    if (!document.querySelector(".guest-lobby")) return;               // a game took the screen meanwhile
    l = l || await loadLobby();
    if (!l) return invalid();
    if (!l.offline) saveMe({ ...me, ...l.profile });
    if (!document.querySelector(".guest-lobby")) return;
    draw(l);
    lobbyTimer = setTimeout(() => poll(), 3000);
  };
  poll(first);
}

function play(me, game) {
  window.FQ_GUEST_AVATAR = () => myAvatarDialog(game);                // ☰ › «My avatar» (shared/ui.js openGameMenu)
  const box = h("div" + ({ bingo: ".bingo-live", poker: ".poker-live", tschau: ".cards-live", karussell: ".cards-live", domino: ".dm-live", paarjagd: ".pj-live", werbinich: ".wb-live", kartenlauf: ".kl-live", stadtland: ".sl-live", zeichnen: ".zr-live", wuerfel: ".fw-live", heimwaerts: ".hw-live", jump: ".ju-live", sternlauf: ".sr-live", snack: ".sn-live", verkehr: ".vk-live", klatsch: ".kb-live", verboten: ".vw-live", jass: ".ja-live", werwolf: ".ww-live", schach: ".ch-live", dorfmarkt: ".mk-live", escape: ".er-live", stempeljagd: ".sj-live" }[game] || ".quiz-live"));
  screen(box);
  clearTimeout(lobbyTimer);
  const back = () => lobby();                                           // after the game: back in the lobby
  // a table closed before it started (the game view would wait for its start): back in the lobby by itself –
  // a game that ran ends on its own result screen («Back» leads to the lobby)
  let was = null;
  const watch = async () => {
    if (!box.isConnected) return;
    const l = await loadLobby();
    if (!box.isConnected) return;
    if (!l) return invalid();
    const t = l.tables.find(x => x.game === game && x.joined);
    if (t) was = t.status;
    else if (was === "lobby" && !l.offline) { toast(T("Game ended")); return lobby(l); }
    lobbyTimer = setTimeout(watch, 4000);
  };
  lobbyTimer = setTimeout(watch, 1500);
  if (game === "tschau" || game === "karussell") return cardsLive(box, me, back, game);
  if (game === "domino") return dominoLive(box, me, back);
  if (game === "paarjagd") return paarjagdLive(box, me, back);
  if (game === "werbinich") return werbinichLive(box, me, back);
  if (game === "kartenlauf") return kartenlaufLive(box, me, back);
  if (game === "stadtland") return stadtlandLive(box, me, back);
  if (game === "zeichnen") return zeichnenLive(box, me, back);
  if (game === "wuerfel") return wuerfelLive(box, me, back);
  if (game === "heimwaerts") return heimwaertsLive(box, me, back);
  if (game === "jump") return jumpLive(box, me, back);
  if (game === "sternlauf") return sternlaufLive(box, me, back);
  if (game === "snack") return snackLive(box, me, back);
  if (game === "verkehr") return vkLive(box, me, back);
  if (game === "langstrecke") return langstreckeLive(box, me, back);
  if (game === "klatsch") return klatschLive(box, me, back);
  if (game === "verboten") return verbotenLive(box, me, back);
  if (game === "jass") return jassLive(box, me, back);
  if (game === "werwolf") return werwolfLive(box, me, back);
  if (game === "schach") return schachLive(box, me, back);
  if (game === "dorfmarkt") return dorfmarktLive(box, me, back);
  if (game === "escape") return escapeLive(box, me, back);
  if (game === "stempeljagd") return stempeljagdLive(box, me, back);
  ({ bingo: bingoLive, poker: pokerLive, song: songLive }[game] || quizLive)(box, me, back);
}

I18N.ready.then(start);
