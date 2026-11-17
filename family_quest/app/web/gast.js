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

async function start() {
  let info;
  try { info = await api("community/guest/info?code=" + encodeURIComponent(CODE)); }
  catch (e) {
    if (me && Auth.kid) return play(me, sessionStorage.getItem("fq.guest.game") || "quiz");      // the game just ended – show the result
    return screen(h("section.card.center", h("div.big-ic", "🎲"), h("h2", T("This invitation is not valid (any more)")),
      h("p.muted", T("Ask the family for a new QR code."))));
  }
  if (me && Auth.kid) return play(me, info.game);
  const name = h("input", { type: "text", maxlength: 20, autocomplete: "nickname", placeholder: I18N.tr(T("Your name")) });
  const go = async () => {
    if (!name.value.trim()) return name.focus();
    try {
      const r = await api("community/guest/join", { method: "POST", body: { code: CODE, name: name.value } });
      Auth.kid = r.token; me = r.profile;
      sessionStorage.setItem("fq.guest.me", JSON.stringify(me)); sessionStorage.setItem("fq.guest.game", r.game);
      play(me, r.game);
    } catch (e) { toast(e.message, "bad"); }
  };
  name.addEventListener("keydown", e => { if (e.key === "Enter") go(); });
  screen(h("section.card.center.guest-join",
    h("img", { src: "img/icon.svg", alt: "", width: 64, height: 64 }),
    h("h1", { bingo: "🎱 Bingo", poker: "🃏 Texas Hold'em", tschau: "🂡 Tschau Sepp", karussell: "🎠 Kartenkarussell", song: "🎵 Errate den Song", domino: "🁫 Domino", paarjagd: "🧠 " + I18N.tr(T("Pair Hunt")), werbinich: "🎭 " + I18N.tr(T("Who am I?")), kartenlauf: "🏁 Kartenlauf", stadtland: "🏙️ " + I18N.tr(T("City, Country, River")), zeichnen: "🎨 " + I18N.tr(T("Draw & Guess")), wuerfel: "🎲 " + I18N.tr(T("Five Dice")), heimwaerts: "🏠 " + I18N.tr(T("Homeward")), jump: "🦘 Jump", sternlauf: "🌠 " + I18N.tr(T("Star Runner")), snack: "🍔 " + I18N.tr(T("Snack Rush")), verkehr: "🚦 " + I18N.tr(T("Traffic Cadet")), klatsch: "👏 " + I18N.tr(T("Clap the Beat")), verboten: "🚫 " + I18N.tr(T("Forbidden Words")), jass: "♣️ " + I18N.tr(T("Jass")), werwolf: "🐺 " + I18N.tr(T("Werewolves")), schach: "♟️ " + I18N.tr(T("Chess")), dorfmarkt: "🏘️ " + I18N.tr(T("Village Market")), escape: "🗝️ " + I18N.tr(T("Escape Room")) }[info.game] || "🎯 ", info.game === "quiz" ? C(info.title) : null),
    h("p", T("You are invited to play along! What is your name?")),
    name, h("button.btn.big", { onclick: go }, "🙋 ", T("Join")),
    h("div.row.center", langPicker())));
  name.focus();
}

function play(me, game) {
  const box = h("div" + ({ bingo: ".bingo-live", poker: ".poker-live", tschau: ".cards-live", karussell: ".cards-live", domino: ".dm-live", paarjagd: ".pj-live", werbinich: ".wb-live", kartenlauf: ".kl-live", stadtland: ".sl-live", zeichnen: ".zr-live", wuerfel: ".fw-live", heimwaerts: ".hw-live", jump: ".ju-live", sternlauf: ".sr-live", snack: ".sn-live", verkehr: ".vk-live", klatsch: ".kb-live", verboten: ".vw-live", jass: ".ja-live", werwolf: ".ww-live", schach: ".ch-live", dorfmarkt: ".mk-live", escape: ".er-live" }[game] || ".quiz-live"));
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
  if (game === "klatsch") return klatschLive(box, me, back);
  if (game === "verboten") return verbotenLive(box, me, back);
  if (game === "jass") return jassLive(box, me, back);
  if (game === "werwolf") return werwolfLive(box, me, back);
  if (game === "schach") return schachLive(box, me, back);
  if (game === "dorfmarkt") return dorfmarktLive(box, me, back);
  if (game === "escape") return escapeLive(box, me, back);
  ({ bingo: bingoLive, poker: pokerLive, song: songLive }[game] || quizLive)(box, me, back);
}

I18N.ready.then(start);
