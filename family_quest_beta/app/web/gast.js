// Guest page: friends and grandparents scan the QR code of a running family game, type a name and play along.
// Only the game is open to them – the guest token is not a family login (it lives in this tab only).
"use strict";
const app = document.getElementById("app");
const CODE = new URLSearchParams(location.search).get("c") || "";
// the shared game views ask Auth.kid for the token: here it is the guest token of this tab
Object.defineProperty(Auth, "kid", {
  get() { try { return sessionStorage.getItem("fq.guest") || ""; } catch { return ""; } },
  set(v) { try { v ? sessionStorage.setItem("fq.guest", v) : sessionStorage.removeItem("fq.guest"); } catch {} },
});
Object.defineProperty(Auth, "parent", { get: () => "", set() {} });
const screen = (...xs) => app.replaceChildren(h("main.guest-main", ...xs.flat().filter(Boolean)));
let me = null;
try { me = JSON.parse(sessionStorage.getItem("fq.guest.me") || "null"); } catch {}
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
        me = { ...me, avatar: r.avatar }; sessionStorage.setItem("fq.guest.me", JSON.stringify(me));
        m.close(); toast(T("Saved"), "good"); play(me, game);                 // draw the table anew with the new seat
      } catch (e) { toast(e.message, "bad"); }
    } }, "💾 ", T("Save")), h("button.btn.ghost", { type: "button", onclick: () => m.close() }, T("Cancel")))));
}

async function start() {
  let info;
  try { info = await api("community/guest/info?code=" + encodeURIComponent(CODE)); }
  catch (e) {
    if (me && Auth.kid) return play(me, sessionStorage.getItem("fq.guest.game") || "quiz");      // the game just ended – show the result
    return screen(h("section.card.center", h("div.big-ic", "🎲"), h("h2", T("This invitation is not valid (any more)")),
      h("p.muted", T("Ask the family for a new QR code."))));
  }
  catalog = info.avatar_catalog || null;
  if (me && Auth.kid) return play(me, info.game);
  const look = avatarPicker();
  const name = h("input", { type: "text", maxlength: 20, autocomplete: "nickname", placeholder: I18N.tr(T("Your name")) });
  const go = async () => {
    if (!name.value.trim()) return name.focus();
    try {
      const r = await api("community/guest/join", { method: "POST", body: { code: CODE, name: name.value, avatar: look.value() } });
      Auth.kid = r.token; me = r.profile;
      sessionStorage.setItem("fq.guest.me", JSON.stringify(me)); sessionStorage.setItem("fq.guest.game", r.game);
      play(me, r.game);
    } catch (e) { toast(e.message, "bad"); }
  };
  name.addEventListener("keydown", e => { if (e.key === "Enter") go(); });
  screen(h("section.card.center.guest-join",
    h("img", { src: "img/icon.svg", alt: "", width: 64, height: 64 }),
    h("h1", { bingo: "🎱 Bingo", poker: "🃏 Texas Hold'em", tschau: "🂡 Tschau Sepp", karussell: "🎠 " + I18N.tr(T("Card Carousel")), song: "🎵 " + I18N.tr(T("Guess the song")), domino: "🁫 Domino", paarjagd: "🧠 " + I18N.tr(T("Pair Hunt")), werbinich: "🎭 " + I18N.tr(T("Who am I?")), kartenlauf: "🏁 " + I18N.tr(T("Card Race")), stadtland: "🏙️ " + I18N.tr(T("City, Country, River")), zeichnen: "🎨 " + I18N.tr(T("Draw & Guess")), wuerfel: "🎲 " + I18N.tr(T("Five Dice")), heimwaerts: "🏠 " + I18N.tr(T("Homeward")), jump: "🦘 Jump", sternlauf: "🌠 " + I18N.tr(T("Star Runner")), snack: "🍔 " + I18N.tr(T("Snack Rush")), verkehr: "🚦 " + I18N.tr(T("Traffic Cadet")), langstrecke: "🏎️ " + I18N.tr(T("24h Endurance")), klatsch: "👏 " + I18N.tr(T("Clap the Beat")), verboten: "🚫 " + I18N.tr(T("Forbidden Words")), jass: "♣️ " + I18N.tr(T("Jass")), werwolf: "🐺 " + I18N.tr(T("Werewolves")), schach: "♟️ " + I18N.tr(T("Chess")), dorfmarkt: "🏘️ " + I18N.tr(T("Village Market")), escape: "🗝️ " + I18N.tr(T("Escape Room")), stempeljagd: "🏛️ " + I18N.tr(T("Beat the Bureaucracy")) }[info.game] || "🎯 ", info.game === "quiz" ? C(info.title) : null),
    h("p", T("You are invited to play along! What is your name?")),
    name, h("p.small.muted.guest-av-q", T("Pick your avatar:")), look.el, h("button.btn.big", { onclick: go }, "🙋 ", T("Join")),
    h("div.row.center", langPicker())));
  name.focus();
}

function play(me, game) {
  window.FQ_GUEST_AVATAR = () => myAvatarDialog(game);                // ☰ › «My avatar» (shared/ui.js openGameMenu)
  const box = h("div" + ({ bingo: ".bingo-live", poker: ".poker-live", tschau: ".cards-live", karussell: ".cards-live", domino: ".dm-live", paarjagd: ".pj-live", werbinich: ".wb-live", kartenlauf: ".kl-live", stadtland: ".sl-live", zeichnen: ".zr-live", wuerfel: ".fw-live", heimwaerts: ".hw-live", jump: ".ju-live", sternlauf: ".sr-live", snack: ".sn-live", verkehr: ".vk-live", klatsch: ".kb-live", verboten: ".vw-live", jass: ".ja-live", werwolf: ".ww-live", schach: ".ch-live", dorfmarkt: ".mk-live", escape: ".er-live", stempeljagd: ".sj-live" }[game] || ".quiz-live"));
  screen(box);
  const back = () => screen(h("section.card.center", h("div.big-ic", "👋"), h("h2", T("Thanks for playing!")),
    h("button.btn", { onclick: () => location.reload() }, T("Back"))));
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
