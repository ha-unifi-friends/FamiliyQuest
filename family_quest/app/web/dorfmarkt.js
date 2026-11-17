// «Dorfmarkt» – a property-trading board game in a Swiss village, live for the family (familyquest/dorfmarkt.py).
// Roll the dice, buy shops and places of the village, build market stands and a market hall, collect rent, trade.
// dorfmarktLive(box, me, back) runs a table (family or alone against bots), dorfmarktStartDialog(solo, onStarted) sets
// the rules. The server rolls the dice and checks every rule – this file draws the board and the tokens.
// Uses botPicker() from cards.js and guestInvite() from community.js.
"use strict";

const MK_ICON = "🏘️";
const mkName = () => I18N.tr(T("Dorfmarkt"));
const mkCoins = list => list.join(" / ") + " 🪙";
const MK_GROUPS = ["#8fce4a", "#22b3a6", "#c27be0", "#f3b33d", "#4aa3ef", "#f06b5c", "#a77a57", "#d9367a"];   // 8 colour groups
const MK_PLAYERS = ["#e8590c", "#1971c2", "#2f9e44", "#9c36b5", "#e6a700", "#0c8599"];                          // seat 0..5
const MK_PIPS = { 1: [[50, 50]], 2: [[28, 28], [72, 72]], 3: [[26, 26], [50, 50], [74, 74]], 4: [[28, 28], [72, 28], [28, 72], [72, 72]],
  5: [[26, 26], [74, 26], [50, 50], [26, 74], [74, 74]], 6: [[28, 24], [72, 24], [28, 50], [72, 50], [28, 76], [72, 76]] };
// the names of the fields (the server only knows keys, prices and rents)
const MK_FIELD = {
  markttag: ["🧺", T("Market day")], townhall: ["🏛️", T("Town hall")], square: ["⛲", T("Village square")], gomeeting: ["👉", T("Off to the town meeting")],
  farmshop: ["🥕", T("Farm shop")], beehouse: ["🐝", T("Bee house")], icecream: ["🍦", T("Ice cream stand")], kiosk: ["📰", T("Station kiosk")],
  bakery: ["🥖", T("Bakery")], pastry: ["🧁", T("Pastry shop")], cheese: ["🧀", T("Cheese dairy")], bikeshop: ["🚲", T("Bike workshop")],
  carpenter: ["🪚", T("Carpentry")], pool: ["🏊", T("Swimming pool")], minigolf: ["⛳", T("Mini golf")], climbing: ["🧗", T("Climbing park")],
  villageshop: ["🛒", T("Village shop")], flowers: ["💐", T("Flower shop")], hairdresser: ["💇", T("Hairdresser")], bookshop: ["📚", T("Bookshop")],
  toyshop: ["🧸", T("Toy shop")], inn: ["🍲", T("Village inn")], chocolate: ["🍫", T("Chocolate workshop")], watchmaker: ["⌚", T("Watchmaker")],
  bus_school: ["🚌", T("Village bus: School")], bus_church: ["🚌", T("Village bus: Church")], bus_station: ["🚌", T("Village bus: Station")], bus_alp: ["🚌", T("Village bus: Alp")],
  power: ["⚡", T("Electricity works")], water: ["💧", T("Waterworks")], tax: ["🏛️", T("Municipal tax")], club: ["🎺", T("Club fee")],
  zufall: ["❓", T("Surprise")], dorfkasse: ["💰", T("Village fund")],
};
const MK_CARDS = {
  z_markttag: T("Off to the market! Go to Market day and collect 200 Taler."), z_postauto: T("Hop on the village bus: go to the next stop."),
  z_pool: T("What a hot day! Go to the swimming pool."), z_back3: T("Oops, you forgot your shopping bag – go back 3 fields."),
  z_snow: T("You found 50 Taler in the snow."), z_tyre: T("Flat tyre! The repair costs 15 Taler."), z_meeting: T("Off to the town meeting!"),
  z_free: T("Free pass: you may leave the town meeting at once. Keep this card."), z_sackrace: T("You won the sack race: +100 Taler."),
  z_cleaning: T("Spring cleaning: pay 25 Taler per market stand and 100 per market hall."), z_watch: T("Your watch is broken – visit the watchmaker."),
  z_icecream: T("You buy everybody an ice cream: pay every player 20 Taler."),
  d_counted: T("The village fund counted wrong – in your favour: +150 Taler."), d_birthday: T("Happy birthday! Every player gives you 10 Taler."),
  d_library: T("Your library book is late: pay 20 Taler."), d_flea: T("You sold old toys at the flea market: +60 Taler."),
  d_markttag: T("Off to the market! Go to Market day and collect 200 Taler."), d_free: T("Free pass: you may leave the town meeting at once. Keep this card."),
  d_meeting: T("Off to the town meeting!"), d_garden: T("Prize for the nicest garden: +50 Taler."), d_music: T("Music school: pay 50 Taler."),
  d_grandma: T("Pocket money from grandma: +100 Taler."), d_trip: T("The class trip costs 40 Taler."),
  d_road: T("Road works in the village: pay 20 Taler per market stand and 60 per market hall."),
};
let MK_BOARD = null;                                    // from the server: [{t, key, g, price, rent, house, amount}]
const mkField = f => (MK_BOARD && MK_BOARD[f]) || {};
const mkFieldName = f => I18N.tr((MK_FIELD[mkField(f).key] || ["", "?"])[1]);
const mkFieldIcon = f => (MK_FIELD[mkField(f).key] || ["❔"])[0];
const mkMoney = n => Number(n || 0).toLocaleString("de-CH") + " Taler";
const mkTaler = n => h("span.mk-taler", { translate: "no" }, h("i", "T"), Number(n || 0).toLocaleString("de-CH"));

// ---------------------------------------------------------------- the board (viewBox 0 0 1120 1120)
// 36 fields clockwise from the bottom left corner: corners 160 × 160, the other fields 100 × 160.
function mkRect(f) {
  const C = 160, W = 100;
  if (f === 0) return { x: 0, y: 960, w: C, h: C, side: 0, corner: true };
  if (f < 9) return { x: 0, y: 960 - f * W, w: C, h: W, side: 0 };                    // left side, upwards
  if (f === 9) return { x: 0, y: 0, w: C, h: C, side: 1, corner: true };
  if (f < 18) return { x: C + (f - 10) * W, y: 0, w: W, h: C, side: 1 };              // top, to the right
  if (f === 18) return { x: 960, y: 0, w: C, h: C, side: 2, corner: true };
  if (f < 27) return { x: 960, y: C + (f - 19) * W, w: C, h: W, side: 2 };            // right side, downwards
  if (f === 27) return { x: 960, y: 960, w: C, h: C, side: 3, corner: true };
  return { x: 960 - (f - 27) * W, y: 960, w: W, h: C, side: 3 };                     // bottom, to the left
}
const mkCenter = f => { const r = mkRect(f); return [r.x + r.w / 2, r.y + r.h / 2]; };
// the colour band lies on the inner edge of a field
function mkBand(r, depth) {
  if (r.side === 0) return { x: r.x + r.w - depth, y: r.y, w: depth, h: r.h };
  if (r.side === 1) return { x: r.x, y: r.y + r.h - depth, w: r.w, h: depth };
  if (r.side === 2) return { x: r.x, y: r.y, w: depth, h: r.h };
  return { x: r.x, y: r.y, w: r.w, h: depth };
}
function mkOuter(r, depth) {
  if (r.side === 0) return { x: r.x, y: r.y, w: depth, h: r.h };
  if (r.side === 1) return { x: r.x, y: r.y, w: r.w, h: depth };
  if (r.side === 2) return { x: r.x + r.w - depth, y: r.y, w: depth, h: r.h };
  return { x: r.x, y: r.y + r.h - depth, w: r.w, h: depth };
}
const mkEsc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function mkBoardSvg() {
  const p = [`<rect x="0" y="0" width="1120" height="1120" rx="28" class="mk-bg"/>`,
    `<rect x="160" y="160" width="800" height="800" class="mk-mid"/>`];
  // the village in the middle: hills, houses, a church
  p.push(`<path d="M160 760 Q300 640 450 720 T760 690 T960 720 V960 H160 Z" class="mk-hill"/>`,
    `<path d="M160 820 Q360 740 560 800 T960 790 V960 H160 Z" class="mk-hill2"/>`);
  for (const [x, y, s] of [[250, 770, 1], [330, 790, 0.8], [690, 760, 1], [790, 780, 0.85], [860, 770, 0.7]]) {
    p.push(`<g transform="translate(${x} ${y}) scale(${s})" class="mk-house"><rect x="-34" y="-40" width="68" height="52" rx="4"/><path d="M-44 -38 L0 -78 L44 -38 Z" class="mk-roof"/><rect x="-10" y="-14" width="20" height="26" class="mk-door"/></g>`);
  }
  p.push(`<g transform="translate(520 760)" class="mk-house"><rect x="-30" y="-70" width="60" height="82" rx="4"/><path d="M-36 -68 L0 -150 L36 -68 Z" class="mk-roof"/><circle cx="0" cy="-42" r="11" class="mk-door"/></g>`);
  for (let f = 0; f < 36; f++) {
    const r = mkRect(f), fd = mkField(f);
    p.push(`<g class="mk-f" data-f="${f}"><rect x="${r.x}" y="${r.y}" width="${r.w}" height="${r.h}" class="mk-cell${r.corner ? " mk-corner" : ""} mk-t-${fd.t}"/>`);
    if (fd.t === "prop") { const b = mkBand(r, 34); p.push(`<rect x="${b.x}" y="${b.y}" width="${b.w}" height="${b.h}" style="fill:${MK_GROUPS[fd.g]}" class="mk-band"/>`); }
    const [cx, cy] = mkCenter(f);
    if (r.corner) {
      p.push(`<text x="${cx}" y="${cy + 6}" class="mk-cic">${(MK_FIELD[fd.key] || ["?"])[0]}</text>`);
      const label = mkFieldName(f), fit = label.length > 13 ? ` textLength="148" lengthAdjust="spacingAndGlyphs"` : "";
      p.push(`<text x="${cx}" y="${cy + 58}" class="mk-clabel"${fit}>${mkEsc(label)}</text>`);
    } else {
      // the icon a little towards the outside (the band is inside)
      const off = fd.t === "prop" ? 14 : 0, d = [[-off, 0], [0, -off], [off, 0], [0, off]][r.side];
      p.push(`<text x="${cx + d[0]}" y="${cy + d[1] + 16}" class="mk-ic">${(MK_FIELD[fd.key] || ["?"])[0]}</text>`);
    }
    p.push(`</g>`);
  }
  p.push(`<text x="560" y="300" class="mk-logo">${mkEsc(mkName())}</text>`);
  return p.join("");
}
// owners (a tab on the outer edge in the player's colour), buildings (on the band), mortgages
function mkMarksSvg(st) {
  const p = [], seatOf = id => (st.players.find(x => x.id === id) || {}).seat ?? 0;
  for (const [k, pid] of Object.entries(st.owner || {})) {
    const f = +k, r = mkRect(f), o = mkOuter(r, 16), col = MK_PLAYERS[seatOf(pid) % 6];
    p.push(`<rect x="${o.x}" y="${o.y}" width="${o.w}" height="${o.h}" style="fill:${col}" class="mk-own"/>`);
    if ((st.mortgaged || []).includes(f)) p.push(`<rect x="${r.x + 3}" y="${r.y + 3}" width="${r.w - 6}" height="${r.h - 6}" class="mk-mort"/>`);
    const n = +(st.build || {})[k] || 0;
    if (!n) continue;
    const b = mkBand(r, 34), vert = r.side === 0 || r.side === 2;
    if (n === 5) {
      p.push(`<rect x="${b.x + 4}" y="${b.y + 4}" width="${b.w - 8}" height="${b.h - 8}" rx="6" class="mk-hall"/>`);
      p.push(`<text x="${b.x + b.w / 2}" y="${b.y + b.h / 2 + 8}" class="mk-hallic">★</text>`);
    } else for (let i = 0; i < n; i++) {
      const s = 19, gap = (vert ? b.h : b.w) / 4;
      const x = vert ? b.x + (b.w - s) / 2 : b.x + gap * i + (gap - s) / 2, y = vert ? b.y + gap * i + (gap - s) / 2 : b.y + (b.h - s) / 2;
      p.push(`<rect x="${x}" y="${y}" width="${s}" height="${s}" rx="3" class="mk-stand"/>`);
    }
  }
  return p.join("");
}
function mkDieSvg(v) {
  const pips = (MK_PIPS[v] || []).map(([x, y]) => `<circle cx="${x}" cy="${y}" r="9"/>`).join("");
  return `<svg viewBox="0 0 100 100" aria-hidden="true"><rect x="5" y="5" width="90" height="90" rx="20" class="mk-face"/>${pips}</svg>`;
}

function dorfmarktRulesView(r, rewards) {
  r = r || {};
  const end = r.mode === "classic" ? T("The game goes on until only one player is left – the others are bankrupt.")
    : r.mode === "time" ? I18N.tr(T("After {0} minutes the richest player wins (Taler + fields + buildings).")).replace("{0}", r.minutes || 60)
      : I18N.tr(T("After {0} rounds the richest player wins (Taler + fields + buildings).")).replace("{0}", r.rounds || 30);
  const items = [
    I18N.tr(T("Everybody starts with {0} and walks around the village with two dice.")).replace("{0}", mkMoney(r.money || 1500)),
    T("Passing or landing on Market day brings 200 Taler."),
    T("A double rolls again – the third double in a row sends you to the town meeting."),
    r.auction ? T("Land on a free shop or place: buy it – or it is auctioned: everybody raises the price by 10, 25 or 50; 5 seconds after the last bid the highest bid wins.") : T("Land on a free shop or place: buy it or leave it."),
    T("Land on a field of another player: pay the rent. With the whole colour group the rent doubles."),
    T("With a whole colour group you may build market stands (up to 4, evenly) and then a market hall – the rent grows a lot."),
    T("Village bus: 25 / 50 / 100 / 200 Taler for 1 to 4 stops. Works: 4 × the dice, with both works 10 × the dice."),
    T("Town meeting: pay 50 Taler, use a free pass or try to roll a double (3 tries)."),
    T("Surprise and Village fund: draw a card."),
    r.mortgage !== false ? T("Short of Taler? Sell buildings for half the price or mortgage a field for half its price (no rent while mortgaged).") : T("Short of Taler? Sell buildings for half the price."),
    T("Trade: offer fields and Taler to another player – they accept or decline."),
    T("Who cannot pay is bankrupt and out of the game."),
    end,
    rewards ? I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", mkCoins(rewards)) : null,
    T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."),
  ].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

async function dorfmarktStartDialog(solo, onStarted) {
  let r = {};
  try { r = await api("community/dorfmarkt/rules"); } catch {}
  const sel = (v, list) => h("select", ...list.map(([k, n]) => h("option", { value: k, selected: String(v) === String(k) }, n)));
  const bots = sel(solo ? Math.max(1, r.bots ?? 2) : (r.bots ?? 0), (solo ? [1, 2, 3, 4, 5] : [0, 1, 2, 3, 4, 5]).map(n => [n, String(n)]));
  const level = sel(r.level || "normal", [["easy", T("easy")], ["normal", T("normal")], ["hard", T("hard")]]);
  const curLen = r.mode === "classic" ? "classic" : r.mode === "time" ? "t" + (r.minutes || 60) : "r" + (r.rounds || 30);
  const length = sel(curLen, [["r10", I18N.tr(T("{0} rounds")).replace("{0}", 10)], ["r20", I18N.tr(T("{0} rounds")).replace("{0}", 20)],
    ["r30", I18N.tr(T("{0} rounds")).replace("{0}", 30)], ["r50", I18N.tr(T("{0} rounds")).replace("{0}", 50)],
    ["t30", I18N.tr(T("{0} minutes")).replace("{0}", 30)], ["t45", I18N.tr(T("{0} minutes")).replace("{0}", 45)],
    ["t60", I18N.tr(T("{0} minutes")).replace("{0}", 60)], ["t90", I18N.tr(T("{0} minutes")).replace("{0}", 90)],
    ["classic", T("Classic: until one is left")]]);
  const money = sel(r.money || 1500, [[1000, mkMoney(1000)], [1500, mkMoney(1500)], [2000, mkMoney(2000)]]);
  const chk = v => h("input", { type: "checkbox", checked: !!v });
  const auction = chk(r.auction), mortgage = chk(r.mortgage !== false);
  const picker = botPicker(r.bot_ms);
  const rw = r.rewards || [0, 0, 0];
  const coins = solo ? h("p.small.muted", "🪙 ", T("Alone against bots there are no coins."))
    : rw.some(x => x > 0) ? h("p.small.pj-coins", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", mkCoins(rw)), h("br"),
      h("span.muted", T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."))) : null;
  const m = modal(h("div.form", h("h2", MK_ICON, " ", mkName(), solo ? " – " + I18N.tr(T("alone against bots")) : ""),
    h("p.small.muted", T("Buy the shops of the village, build market stands and collect rent – who is the richest at the end?")),
    h("div.grid2", h("label.field", T("Bots"), bots), h("label.field", T("Bots play"), level),
      h("label.field", T("Game length"), length), h("label.field", T("Taler at the start"), money)),
    solo ? null : h("p.small.muted", T("2 to 6 players: the family joins on their own devices, guests via QR code.")),
    h("div.cards-rules",
      h("label.check", auction, T("Auction: a field nobody buys goes to the highest bid")),
      h("label.check", mortgage, T("Mortgages allowed"))),
    picker.el,
    coins,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      const len = length.value, body = { solo, bots: Math.max(+bots.value, picker.ids().length), level: level.value, auction: auction.checked,
        mortgage: mortgage.checked, money: +money.value, bot_ids: picker.ids(), bot_ms: picker.ms() };
      if (len === "classic") body.mode = "classic";
      else if (len[0] === "t") Object.assign(body, { mode: "time", minutes: +len.slice(1) });
      else Object.assign(body, { mode: "rounds", rounds: +len.slice(1) });
      try { await api("community/dorfmarkt/start", { method: "POST", body }); m.close(); onStarted(); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", solo ? T("Play") : T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
}

function dorfmarktLive(box, me, back) {
  let st = null, timer = null, alive = true, lastSig = "", cheered = false, busy = false, rolling = false;
  let board = null, boardKey = "", marksKey = "", tokens = {}, shownPos = {}, seenSeq = null, zoom = false;
  let openTrade = null, seenRoll = null;
  const sheets = new Set();                              // open field cards / lists: redrawn with every new state
  const myId = String(me.id);
  box.classList.add("mk-live");
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => { alive = false; clearTimeout(timer); box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open"); };
  window.addEventListener("hashchange", stop, { once: true });
  const player = id => (st && st.players || []).find(p => p.id === id) || {};
  const who = id => player(id).name || "?";
  const colorOf = id => MK_PLAYERS[(player(id).seat ?? 0) % 6];
  const mine = () => player(myId);
  const openModal = view => { const m = modal(h("div", view, h("button.btn", { onclick: () => m.close() }, T("Close")))); return m; };
  const tr = (s, ...a) => a.reduce((t, v, i) => t.split("{" + i + "}").join(v), I18N.tr(s));
  const say = text => h("span", { translate: "no" }, text);
  const act = async (action, data = {}) => {
    if (busy) return null;
    busy = true;
    try { st = await api("community/dorfmarkt/act", { method: "POST", body: { action, ...data } }); return st; }
    catch (e) { toast(e.message, "bad"); return null; }
    finally { busy = false; draw(true); sheets.forEach(x => x.refresh()); }
  };
  const lead = async (path, body) => {
    try { st = await api("community/dorfmarkt/" + path, { method: "POST", body }); } catch (e) { toast(e.message, "bad"); }
    draw(true);
  };
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try {
      if (!MK_BOARD) MK_BOARD = await api("community/dorfmarkt/board");
      const s = await api("community/dorfmarkt");
      if (!rolling && !busy) { st = s; draw(); sheets.forEach(x => x.refresh()); }
    } catch {}
    timer = setTimeout(poll, 900);
  }

  // ---------- the board: built once per game; owners, buildings and tokens are updated
  function buildBoard() {
    const key = String(st.game);
    if (board && key === boardKey) return;
    boardKey = key; marksKey = ""; tokens = {}; shownPos = {};
    const svg = `<svg viewBox="0 0 1120 1120" xmlns="http://www.w3.org/2000/svg" class="mk-svg">${mkBoardSvg()}<g class="mk-marks"></g></svg>`;
    board = h("div.mk-board", { html: svg },
      h("div.mk-center", h("div.mk-info"), h("div.mk-dice"), h("div.mk-lastline")),
      h("div.mk-tokens"));
    board.querySelector("svg").addEventListener("click", e => {
      const g = e.target.closest(".mk-f");
      if (g) fieldCard(+g.dataset.f);
    });
    board.querySelector(".mk-dice").addEventListener("click", () => { if (st && st.can_roll && !st.in_meeting) roll(); });
  }
  function updateBoard() {
    const mk = JSON.stringify([st.owner, st.build, st.mortgaged]);
    if (mk !== marksKey) { marksKey = mk; board.querySelector(".mk-marks").innerHTML = mkMarksSvg(st); }
    board.classList.toggle("mk-zoomed", zoom);
    // the middle: round / time, the dice, what happened last
    const info = board.querySelector(".mk-info");
    const parts = [];
    if (st.paused) parts.push("⏸ " + I18N.tr(T("Paused")));
    else if (st.rules.mode === "rounds") parts.push(tr(T("Round {0} of {1}"), Math.min(st.round, st.rules.rounds), st.rules.rounds));
    else if (st.rules.mode === "time" && st.time_left != null) parts.push("⏱ " + Math.floor(st.time_left / 60) + ":" + String(st.time_left % 60).padStart(2, "0"));
    else parts.push(tr(T("Round {0}"), st.round));
    info.replaceChildren(say(parts.join(" · ")));
    const dice = board.querySelector(".mk-dice");
    if (!rolling) {
      const d = st.dice || [0, 0];
      dice.innerHTML = `<span class="mk-die">${mkDieSvg(d[0])}</span><span class="mk-die">${mkDieSvg(d[1])}</span>`;
      if (st.roll_seq !== seenRoll && seenRoll !== null && st.dice) dice.classList.add("tumble"), setTimeout(() => dice.classList.remove("tumble"), 450);
      seenRoll = st.roll_seq;
    }
    dice.classList.toggle("go", !!(st.can_roll && !st.in_meeting));
    dice.style.setProperty("--pc", colorOf(st.turn));
    const lt = lastText(st.last);
    board.querySelector(".mk-lastline").replaceChildren(...(lt ? [say(lt)] : []));
    updateTokens();
  }
  function tokenXY(f, k, n) {
    const [cx, cy] = mkCenter(f), r = mkRect(f);
    const off = n > 1 ? [[-1, -1], [1, -1], [-1, 1], [1, 1], [0, 0], [0, -1]][k % 6] : [0, 0];
    const s = r.corner ? 34 : 24;
    return [(cx + off[0] * s) / 11.2, (cy + off[1] * s) / 11.2];
  }
  function updateTokens() {
    const layer = board.querySelector(".mk-tokens");
    const act = st.players.filter(p => !p.out);
    const byField = {};
    for (const p of act) (byField[p.pos] = byField[p.pos] || []).push(p.id);
    for (const p of st.players) {
      let el = tokens[p.id];
      if (p.out) { if (el) { el.remove(); delete tokens[p.id]; } continue; }
      if (!el) {
        el = h("div.mk-token", { style: { "--pc": MK_PLAYERS[p.seat % 6] }, title: p.name },
          p.bot ? h("span.mk-tbot", p.emoji || "🤖") : avatarSvg(p.avatar || {}, 26));
        layer.append(el);
        tokens[p.id] = el;
      }
      el.classList.toggle("turn", st.turn === p.id);
      el.classList.toggle("meet", p.meeting != null);
      const list = byField[p.pos] || [p.id], k = list.indexOf(p.id);
      const target = p.pos, from = shownPos[p.id];
      const place = f => { const [x, y] = tokenXY(f, f === target ? k : 0, f === target ? list.length : 1); el.style.left = x + "%"; el.style.top = y + "%"; };
      if (from == null || from === target) { place(target); shownPos[p.id] = target; continue; }
      const steps = (target - from + 36) % 36;
      shownPos[p.id] = target;
      if (steps > 12 || (st.last && st.last.player === p.id && st.last.kind === "meeting")) { place(target); continue; }
      let i = 0;                                         // walk field by field
      const walk = () => { i++; if (!alive) return; place((from + i) % 36); if (i < steps) setTimeout(walk, 140); };
      walk();
    }
  }

  // ---------- rolling
  async function roll() {
    if (!st || !st.can_roll || busy || rolling) return;
    rolling = true;
    const dice = box.querySelector(".mk-dice");
    const spin = dice ? setInterval(() => { dice.innerHTML = `<span class="mk-die">${mkDieSvg(1 + Math.floor(Math.random() * 6))}</span><span class="mk-die">${mkDieSvg(1 + Math.floor(Math.random() * 6))}</span>`; }, 80) : null;
    if (dice) dice.classList.add("rolling");
    try { Sound.play("tap"); } catch {}
    const t0 = Date.now();
    let res = null, err = null;
    busy = true;
    try { res = await api("community/dorfmarkt/act", { method: "POST", body: { action: "roll" } }); } catch (e) { err = e; }
    busy = false;
    await new Promise(ok => setTimeout(ok, Math.max(0, 650 - (Date.now() - t0))));
    clearInterval(spin);
    if (dice) dice.classList.remove("rolling");
    rolling = false;
    if (err) toast(err.message, "bad");
    if (res) { st = res; seenRoll = st.roll_seq; }
    draw(true);
  }

  // ---------- texts
  function cardText(id) { return I18N.tr(MK_CARDS[id] || ""); }
  function lastText(l) {
    if (!l) return "";
    const n = who(l.player), fn = l.field != null ? mkFieldName(l.field) : "";
    switch (l.kind) {
      case "roll": return tr(T("{0} rolled {1} + {2}"), n, l.dice[0], l.dice[1]) + (l.double ? " · " + I18N.tr(T("Double!")) : "");
      case "move": return l.bonus ? tr(T("{0} passed Market day: +{1} Taler"), n, l.bonus) : tr(T("{0} walks to {1}"), n, mkFieldName(l.to));
      case "buy": return tr(T("{0} bought {1} for {2} Taler"), n, fn, l.price);
      case "rent": return tr(T("{0} paid {1} Taler rent to {2}"), n, l.amount, who(l.to));
      case "free_rent": return tr(T("{0} pays no rent – the field is mortgaged"), n);
      case "tax": return tr(T("{0} paid {1} Taler: {2}"), n, l.amount, fn);
      case "card": return (l.deck === "chance" ? "❓ " : "💰 ") + cardText(l.card);
      case "meeting": return tr(T("{0} has to go to the town meeting"), n);
      case "leave": return l.how === "pay" ? tr(T("{0} paid 50 Taler and leaves the town meeting"), n)
        : l.how === "card" ? tr(T("{0} used the free pass"), n)
          : l.how === "double" ? tr(T("{0} rolled a double and leaves the town meeting"), n) : tr(T("{0} paid {1} Taler after three tries"), n, l.amount);
      case "skip": return l.poor ? tr(T("{0} cannot afford {1}"), n, fn) : tr(T("{0} does not buy {1}"), n, fn);
      case "auction_start": return "🔨 " + tr(T("Auction: {0}"), fn);
      case "auction": return l.player ? tr(T("{0} won the auction for {1}: {2} Taler"), n, fn, l.amount) : tr(T("Nobody bid for {0}"), fn);
      case "build": return l.n === 5 ? tr(T("{0} built a market hall on {1}"), n, fn) : tr(T("{0} built a market stand on {1}"), n, fn);
      case "sell": return tr(T("{0} sold a building on {1}"), n, fn);
      case "mortgage": return tr(T("{0} mortgaged {1}"), n, fn);
      case "unmortgage": return tr(T("{0} paid back the mortgage on {1}"), n, fn);
      case "offer": return tr(T("{0} made an offer to {1}"), n, who(l.to));
      case "trade": return "🤝 " + tr(T("{0} and {1} traded"), n, who(l.to));
      case "trade_no": return tr(T("{0} declined the offer"), who(l.to));
      case "trade_failed": return T("The trade did not work out any more");
      case "bankrupt": return "💸 " + tr(T("{0} is bankrupt!"), n);
      default: return "";
    }
  }
  // what happened since the last look: toasts for what concerns me, the card that was drawn
  function news() {
    const log = st.log || [];
    const lastSeq = log.length ? log[log.length - 1].seq : 0;
    if (seenSeq === null) { seenSeq = lastSeq; return; }
    for (const ev of log.filter(e => e.seq > seenSeq)) {
      if (ev.kind === "card") cardPopup(ev);
      else if (ev.kind === "rent" && ev.to === myId) { toast("🪙 " + tr(T("{0} paid you {1} Taler rent"), who(ev.player), ev.amount), "good"); try { Sound.play("right"); } catch {} }
      else if (ev.kind === "rent" && ev.player === myId) toast(lastText(ev), "bad");
      else if (ev.kind === "move" && ev.player === myId && ev.bonus) { toast("🧺 " + lastText(ev), "good"); try { Sound.play("right"); } catch {} }
      else if (ev.kind === "trade" && (ev.to === myId || ev.player === myId)) toast(lastText(ev), "good");
      else if (ev.kind === "trade_no" && ev.player === myId) toast(lastText(ev), "bad");
      else if (ev.kind === "auction" && ev.player === myId) toast(lastText(ev), "good");
      else if (ev.kind === "bankrupt") toast(lastText(ev), ev.player === myId ? "bad" : "");
      else if (ev.kind === "meeting" && ev.player === myId) { toast("🏛️ " + lastText(ev), "bad"); try { Sound.play("wrong"); } catch {} }
    }
    seenSeq = lastSeq;
  }
  function cardPopup(ev) {
    const c = board && board.querySelector(".mk-center");
    if (!c) return;
    const el = h("div.mk-card.mk-" + ev.deck, h("b", ev.deck === "chance" ? "❓ " : "💰 ", ev.deck === "chance" ? T("Surprise") : T("Village fund")),
      h("small", { translate: "no" }, who(ev.player)), h("p", cardText(ev.card)));
    c.append(el);
    setTimeout(() => el.classList.add("out"), 3600);
    setTimeout(() => el.remove(), 4200);
  }

  // ---------- a field: its card (prices, rents, owner) – with the actions for the own fields
  function fieldInfo(f) {
    const fd = mkField(f), own = st.owner[String(f)], b = +(st.build[String(f)] || 0), mort = st.mortgaged.includes(f);
    const head = h("div.mk-fhead", { style: { "--gc": fd.t === "prop" ? MK_GROUPS[fd.g] : "var(--line)" } },
      h("span.mk-fic", mkFieldIcon(f)), h("strong", mkFieldName(f)));
    const rows = [];
    const row = (a, b2, on) => rows.push(h("tr" + (on ? ".on" : ""), h("td", a), h("td.num", b2)));
    if (fd.t === "prop") {
      row(T("Price"), mkMoney(fd.price));
      row(T("Rent"), mkMoney(fd.rent[0]), own && !b);
      row(T("with the whole colour group"), mkMoney(fd.rent[0] * 2));
      row(T("with 1 market stand"), mkMoney(fd.rent[1]), b === 1);
      for (let i = 2; i <= 4; i++) row(tr(T("with {0} market stands"), i), mkMoney(fd.rent[i]), b === i);
      row(T("with a market hall"), mkMoney(fd.rent[5]), b === 5);
      row(T("A market stand costs"), mkMoney(fd.house));
    } else if (fd.t === "bus") {
      row(T("Price"), mkMoney(fd.price));
      [1, 2, 3, 4].forEach(n => row(tr(T("with {0} Village bus stops"), n), mkMoney(25 * 2 ** (n - 1))));
    } else if (fd.t === "util") {
      row(T("Price"), mkMoney(fd.price));
      row(T("with one works"), T("4 × the dice"));
      row(T("with both works"), T("10 × the dice"));
    } else if (fd.t === "tax") row(T("Pay"), mkMoney(fd.amount));
    const text = { start: T("Passing or landing on Market day brings 200 Taler."), jail: T("Just visiting – or sitting in the town meeting: pay 50 Taler, use a free pass or roll a double (3 tries)."),
      free: T("A rest on the village square – nothing happens."), gojail: T("Off to the town meeting!"), chance: T("Surprise and Village fund: draw a card."),
      chest: T("Surprise and Village fund: draw a card.") }[fd.t];
    if (fd.price && st.rules.mortgage) row(T("Mortgage value"), mkMoney(Math.floor(fd.price / 2)));
    const status = own ? h("p.mk-owner", { style: { "--pc": colorOf(own) } }, h("span.mk-dot"), say(tr(T("Owner: {0}"), who(own))),
      mort ? h("b.mk-mortl", " · ", T("mortgaged")) : null,
      b ? h("span", " · ", b === 5 ? "★ " + I18N.tr(T("Market hall")) : "🏠×" + b) : null)
      : fd.price ? h("p.small.muted", T("Nobody owns this field yet.")) : null;
    // the own field, on the own turn: build, sell, mortgage
    const btns = [];
    if (own === myId) {
      if ((st.may_build || []).includes(f)) btns.push(h("button.btn.small", { onclick: () => act("build", { field: f }) }, "🏠+ ", tr(T("Build ({0})"), mkMoney(fd.house))));
      if ((st.may_sell || []).includes(f)) btns.push(h("button.btn.small.ghost", { onclick: () => act("sell", { field: f }) }, "🏠− ", tr(T("Sell ({0})"), mkMoney(Math.floor(fd.house / 2)))));
      if ((st.may_mortgage || []).includes(f)) btns.push(h("button.btn.small.ghost", { onclick: () => act("mortgage", { field: f }) }, "📝 ", tr(T("Mortgage (+{0})"), mkMoney(Math.floor(fd.price / 2)))));
      if ((st.may_unmortgage || []).includes(f)) btns.push(h("button.btn.small.ghost", { onclick: () => act("unmortgage", { field: f }) }, "✅ ", tr(T("Pay back ({0})"), mkMoney(st.unmortgage_cost[String(f)]))));
    }
    return h("div.mk-fcard", head, text ? h("p.small", I18N.tr(text)) : null, rows.length ? h("table.mk-rents", ...rows) : null, status,
      btns.length ? h("div.row.wrap", ...btns) : null);
  }
  function fieldCard(f) {
    if (!st || !MK_BOARD) return;
    const body = h("div"), sheet = { refresh: () => { if (st && st.players && st.owner) body.replaceChildren(fieldInfo(f)); } };
    const m = modal(h("div", body, h("button.btn", { onclick: () => m.close() }, T("Close"))), { onClose: () => sheets.delete(sheet) });
    sheets.add(sheet);
    sheet.refresh();
  }
  // all my fields, by colour group – with build / sell / mortgage
  function myFields() {
    const body = h("div"), sheet = { refresh: () => {
      if (!st || !st.owner) return;
      const fs = Object.keys(st.owner).filter(k => st.owner[k] === myId).map(Number)
        .sort((a, b) => { const fa = mkField(a), fb = mkField(b); return (fa.t === "prop" ? fa.g : 9 + a) - (fb.t === "prop" ? fb.g : 9 + b) || a - b; });
      const rows = fs.map(f => {
        const fd = mkField(f), b = +(st.build[String(f)] || 0), mort = st.mortgaged.includes(f);
        const small = (cls, label, fn, on) => on ? h("button.btn.small" + cls, { onclick: fn }, label) : null;
        return h("div.mk-frow" + (mort ? ".mort" : ""), { style: { "--gc": fd.t === "prop" ? MK_GROUPS[fd.g] : "var(--line)" } },
          h("button.mk-fname", { type: "button", onclick: () => fieldCard(f) }, h("span", mkFieldIcon(f)), " ", h("span", mkFieldName(f)),
            b ? h("small", b === 5 ? " ★" : " " + "🏠".repeat(b)) : null, mort ? h("small.mk-mortl", " · ", T("mortgaged")) : null),
          small("", "🏠+", () => act("build", { field: f }), (st.may_build || []).includes(f)),
          small(".ghost", "🏠−", () => act("sell", { field: f }), (st.may_sell || []).includes(f)),
          small(".ghost", "📝", () => act("mortgage", { field: f }), (st.may_mortgage || []).includes(f)),
          small(".ghost", "✅", () => act("unmortgage", { field: f }), (st.may_unmortgage || []).includes(f)));
      });
      body.replaceChildren(h("h2", "📋 ", T("My fields")), h("p", h("b", T("Taler")), " ", mkTaler(mine().money), " · ", h("span.muted", tr(T("Total worth: {0}"), mkMoney(mine().worth)))),
        rows.length ? h("div.mk-flist", ...rows) : h("p.muted", T("You do not own any field yet.")),
        h("p.small.muted", st.my_turn ? T("🏠+ build a market stand · 🏠− sell one · 📝 mortgage · ✅ pay back. Build only with the whole colour group, evenly.")
          : T("You can build, sell and mortgage on your own turn.")));
    } };
    const m = modal(h("div", body, h("button.btn", { onclick: () => m.close() }, T("Close"))), { onClose: () => sheets.delete(sheet) });
    sheets.add(sheet);
    sheet.refresh();
  }
  // trading: what I give, what I want
  function tradeDialog(to) {
    const others = st.players.filter(p => !p.out && p.id !== myId);
    if (!others.length) return;
    to = to || others[0].id;
    const pick = h("select", ...others.map(p => h("option", { value: p.id, selected: p.id === to }, p.name)));
    const giveM = h("input", { type: "number", min: 0, max: mine().money, step: 10, value: 0, inputmode: "numeric" });
    const wantM = h("input", { type: "number", min: 0, step: 10, value: 0, inputmode: "numeric" });
    const giveBox = h("div.mk-tlist"), wantBox = h("div.mk-tlist");
    const fieldsOf = pid => (st.tradable || []).filter(f => st.owner[String(f)] === pid);
    const boxes = (el, pid) => el.replaceChildren(...(fieldsOf(pid).length ? fieldsOf(pid).map(f => h("label.check.mk-tf", { style: { "--gc": mkField(f).t === "prop" ? MK_GROUPS[mkField(f).g] : "var(--line)" } },
      h("input", { type: "checkbox", value: f }), mkFieldIcon(f), " ", mkFieldName(f))) : [h("span.small.muted", T("no fields to trade"))]));
    const fill = () => { boxes(giveBox, myId); boxes(wantBox, pick.value); wantM.max = player(pick.value).money; };
    pick.addEventListener("change", fill);
    fill();
    const checked = el => [...el.querySelectorAll("input:checked")].map(i => +i.value);
    const m = modal(h("div.form", h("h2", "🤝 ", T("Trade")),
      h("label.field", T("With"), pick),
      h("div.mk-trade", h("div", h("b", T("You give")), giveBox, h("label.field", T("Taler"), giveM)),
        h("div", h("b", T("You want")), wantBox, h("label.field", T("Taler"), wantM))),
      h("p.small.muted", T("Fields with buildings in their colour group cannot be traded.")),
      h("div.row", h("button.btn", { onclick: async () => {
        const res = await act("offer", { to: pick.value, give: checked(giveBox), give_money: +giveM.value || 0, want: checked(wantBox), want_money: +wantM.value || 0 });
        if (res) { m.close(); toast(T("Offer sent"), "good"); }
      } }, "📨 ", T("Send the offer")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  }
  function tradeSummary(t) {
    const list = fs => fs.map(f => mkFieldIcon(f) + " " + mkFieldName(f));
    const side = (fs, money) => [...list(fs), money ? mkMoney(money) : null].filter(Boolean).join(", ") || "–";
    return { give: side(t.give, t.give_money), want: side(t.want, t.want_money) };
  }
  function offerPopup(t) {
    if (openTrade === t.id) return;
    openTrade = t.id;
    const s = tradeSummary(t);
    const m = modal(h("div.form", h("h2", "🤝 ", say(tr(T("{0} makes you an offer"), who(t.from)))),
      h("div.mk-offer", h("div", h("b", T("You get")), h("p", { translate: "no" }, s.give)),
        h("div", h("b", T("You give")), h("p", { translate: "no" }, s.want))),
      h("div.row", h("button.btn", { onclick: async () => { m.close(); await act("answer", { trade: t.id, accept: true }); } }, "✅ ", T("Accept")),
        h("button.btn.ghost", { onclick: async () => { m.close(); await act("answer", { trade: t.id, accept: false }); } }, "✖ ", T("Decline")))),
    { onClose: () => {} });
    return m;
  }

  // ---------- the screen
  function draw(force) {
    if (!alive || !box.isConnected) return;
    if (st && !Array.isArray(st.players)) st = null;
    if (rolling) return;
    const sig = JSON.stringify(st && [st.phase, st.status, st.turn, st.stage, st.roll_seq, st.joined, st.paused, st.round, st.time_left,
      st.players.map(p => [p.id, p.money, p.pos, p.place, p.out, p.meeting]), st.last && st.last.seq, st.auction, st.trades, st.may_build]);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    if (!st) return show(h("section.card.center", h("div.big-ic", MK_ICON), h("h2", T("No game right now")), h("button.btn", { onclick: back }, T("Back"))));
    if (!MK_BOARD) return;
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    // ☰: rules, guests, the actions of whoever leads (pause / resume, end), language
    const lead_ = isHost() && st.status !== "done";
    const menu = gameMenu({ rules: () => dorfmarktRulesView(st.rules, st.coins_on ? st.rewards : null),
      invite: !st.solo && !me.guest && st.status !== "done" ? "dorfmarkt" : null,
      actions: [
        { ic: st.paused ? "▶" : "⏸", label: st.paused ? T("Resume") : T("Pause"), hidden: !lead_ || st.phase !== "play", onclick: () => lead("pause", { on: !st.paused }) },
        { ic: "⏹", label: T("End the game"), danger: true, hidden: !lead_, confirm: T("End the game?"), onclick: () => lead("end").then(() => { stop(); back(); }) }],
      onLeave: running ? () => { stop(); back(); } : null });
    const head = h("div.quiz-head.dm-head", h("div.row.head-title", menu, h("h1", MK_ICON, " ", mkName())), h("div.row",
      st.phase === "play" ? h("button.btn.small.ghost", { onclick: () => { zoom = !zoom; draw(true); }, title: T("Zoom") }, zoom ? "🔎−" : "🔎+") : null));
    // only the main action of the moment stays as a big button: Start in the lobby, Resume in a paused game
    const host = !lead_ ? null
      : st.phase === "lobby" ? h("div.row.center.host-bar", h("button.btn", { onclick: async () => {
          try { const r = await beginGame("community/dorfmarkt/begin", st.players); if (r) { st = r; draw(true); } } catch (e) { toast(e.message, "bad"); }
        } }, "▶ ", T("Start")))
      : st.phase === "play" && st.paused ? h("div.row.center.host-bar", h("button.btn", { onclick: () => lead("pause", { on: false }) }, "▶ ", T("Resume")))
      : null;
    if (st.phase !== "lobby") starterBanner(st.starter, "dorfmarkt");
    if (st.phase === "done" && st.players[0] && st.players[0].money != null) return show(head, result());
    if (st.phase === "done" || st.phase === "lobby" || !st.joined) {
      if (!st.joined && st.phase !== "lobby" && st.phase !== "done") {
        buildBoard(); show(close, head, seats(), h("div.mk-mid", h("div.mk-scroll", board)), h("p.muted.center", T("The game has already started")), host); updateBoard(); return;
      }
      if (!st.joined) return show(close, head, h("section.card.center", h("p", T("Play along on this device?")),
        h("button.btn.big", { onclick: () => lead("join") }, "🙋 ", T("Join"))), lobbySeats(), host);
      return show(close, head, h("section.card.center", h("h2", T("Waiting for the start …")),
        h("p.muted", T("Everybody joins on their own device.")), lobbySeats(),
        st.coins_on ? h("p.small", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", mkCoins(st.rewards))) : null), host);
    }
    buildBoard();
    news();
    show(close, head, seats(), h("div.mk-mid", h("div.mk-scroll" + (zoom ? ".zoom" : ""), board)), feed(), controls(), host);
    updateBoard();
    const inc = (st.trades || []).find(t => t.to === myId);
    if (inc) offerPopup(inc);
  }

  function seatIcon(p, size) {
    return p.bot ? h("span.bot-av", { style: { width: size + "px", height: size + "px", fontSize: (size * 0.6) + "px", background: p.color || null } }, p.emoji || "🤖") : avatarSvg(p.avatar || {}, size);
  }
  function lobbySeats() {
    const free = Array.from({ length: st.bots || 0 }, () => h("div.dm-seat.mk-botseat", h("span.bot-av", { style: { width: "30px", height: "30px", fontSize: "18px" } }, "🤖"), h("span.small.muted", T("Bot"))));
    return h("div.dm-seats", ...st.players.map(p => h("div.dm-seat" + (p.id === myId ? ".dm-me" : ""), seatIcon(p, 30), C(p.name, "strong.small.dm-name"))), ...free);
  }
  function seats() {
    return h("div.mk-seats", ...st.players.map(p => h("button.mk-seat" + (st.turn === p.id ? ".turn" : "") + (p.id === myId ? ".me" : "") + (p.out ? ".out" : ""),
      { type: "button", style: { "--pc": MK_PLAYERS[p.seat % 6] }, onclick: () => playerInfo(p) },
      seatIcon(p, 22),
      h("span.mk-sinfo", C(p.name, "strong.small.mk-sname"),
        h("span.mk-stat", p.out ? "💸" : mkTaler(p.money), p.meeting != null ? " 🏛️" : "", p.free ? " 🎟️" : "")))));
  }
  function playerInfo(p) {
    const fs = Object.keys(st.owner).filter(k => st.owner[k] === p.id).map(Number).sort((a, b) => a - b);
    const m = openModal(h("div", h("h2", seatIcon(p, 30), " ", C(p.name)),
      h("p", mkTaler(p.money), " · ", h("span.muted", tr(T("Total worth: {0}"), mkMoney(p.worth)))),
      p.meeting != null ? h("p", "🏛️ ", T("in the town meeting")) : null,
      fs.length ? h("div.mk-chips", ...fs.map(f => h("button.mk-chip", { type: "button", style: { "--gc": mkField(f).t === "prop" ? MK_GROUPS[mkField(f).g] : "var(--line)" },
        onclick: () => fieldCard(f) }, mkFieldIcon(f), " ", mkFieldName(f), st.mortgaged.includes(f) ? " 📝" : ""))) : h("p.muted", T("No fields yet.")),
      p.id !== myId && !p.out && !mine().out && st.phase === "play" ? h("button.btn.small", { onclick: () => { m.close(); tradeDialog(p.id); } }, "🤝 ", T("Trade")) : null));
  }
  // the last moves (newest first) – below the board, as far as there is room
  function feed() {
    const evs = (st.log || []).filter(e => e !== st.last && e.seq !== (st.last || {}).seq).map(e => [e, lastText(e)]).filter(x => x[1]).slice(-4).reverse();
    return h("div.mk-feed", { translate: "no" }, ...evs.map(([e, t]) => h("div", { style: { "--pc": colorOf(e.player) } }, t)));
  }
  function controls() {
    const my = st.my_turn, stage = st.stage, me2 = mine(), fd = st.joined ? mkField(me2.pos) : {};
    let msg = null;
    const btns = [];
    const B = (label, fn, cls = "") => btns.push(h("button.btn.small" + cls, { onclick: fn }, label));
    const more = () => {
      if (me2.out) return;
      B(["📋 ", T("My fields")], myFields, ".ghost");
      if (st.players.some(p => !p.out && p.id !== myId)) B(["🤝 ", T("Trade")], () => tradeDialog(), ".ghost");
    };
    const a = st.auction;
    if (st.paused) msg = h("strong", "⏸ ", T("The game is paused"));
    else if (me2.out) msg = h("span.muted", "💸 ", T("You are bankrupt – watch the others play."));
    else if (a) {
      // open auction: +10 / +25 / +50 over the current price; 5 seconds after the last bid the highest bid wins
      const f = a.field, lead = a.leader;
      const left = Math.max(0, a.ms), full = (a.seconds || 5) * 1000;
      const barFill = h("i", { style: { width: Math.min(100, left / full * 100) + "%", animationDuration: left + "ms" } });
      const stepBtn = n => h("button.btn.mk-bidbtn", { disabled: a.price + n > me2.money, onclick: () => act("bid", { step: n }) }, "+" + n);
      return h("section.card.mk-ctl.turn", { style: { "--pc": lead ? colorOf(lead) : "var(--accent)" } },
        h("div.mk-msg", h("strong", "🔨 ", say(tr(T("Auction: {0}"), mkFieldIcon(f) + " " + mkFieldName(f)))), " ",
          h("button.btn.small.ghost", { onclick: () => fieldCard(f) }, "ℹ️")),
        h("div.mk-auction",
          h("div.mk-aprice", h("b", mkMoney(a.price)),
            h("span.small", lead ? (lead === myId ? T("You bid the most") : tr(T("{0} bids the most"), who(lead))) : T("No bid yet"))),
          h("div.mk-atime", barFill)),
        me2.out ? null : h("div.row.mk-btns.mk-bids", ...(a.steps || [10, 25, 50]).map(stepBtn)),
        h("div.small.muted", T("5 seconds after the last bid the highest bid gets the field.")));
    }
    else if (my && stage === "roll" && st.in_meeting) {
      msg = h("strong.mk-turnmsg", "🏛️ ", say(tr(T("You are in the town meeting (try {0} of 3)"), (me2.meeting || 0) + 1)));
      B(["🎲 ", T("Roll a double")], roll);
      if (me2.money >= st.bail) B(["💰 ", tr(T("Pay {0}"), mkMoney(st.bail))], () => act("bail"), ".ghost");
      if (me2.free) B(["🎟️ ", T("Use the free pass")], () => act("use_card"), ".ghost");
      more();
    } else if (my && stage === "roll") {
      msg = h("strong.mk-turnmsg", st.doubles ? T("Double – roll again!") : T("Your turn – roll the dice!"));
      B(["🎲 ", T("Roll")], roll);
      if ((st.may_build || []).length) B(["🏠 ", T("Build")], myFields, ".ghost");
      more();
    } else if (my && stage === "buy") {
      const f = me2.pos;
      msg = h("span.mk-buyline", h("button.mk-fmini", { type: "button", style: { "--gc": fd.t === "prop" ? MK_GROUPS[fd.g] : "var(--line)" }, onclick: () => fieldCard(f) },
        mkFieldIcon(f), " ", h("b", mkFieldName(f)), " ℹ️"), " ", say(mkMoney(fd.price)));
      btns.push(h("button.btn.small", { disabled: !st.can_buy, onclick: () => act("buy") }, "🛒 ", tr(T("Buy for {0}"), mkMoney(fd.price))));
      B(st.rules.auction ? ["🔨 ", T("No – auction")] : T("No, thanks"), () => act("skip"), ".ghost");
    } else if (my && stage === "debt") {
      msg = h("strong.mk-debt", "⚠️ ", say(tr(T("You owe {0} – sell or mortgage something"), mkMoney(-me2.money))));
      B(["🪄 ", T("Sell automatically")], () => act("liquidate"));
      B(["📋 ", T("My fields")], myFields, ".ghost");
      B(["💸 ", T("Give up")], () => { if (confirm(I18N.tr(T("Give up? You are bankrupt and out of the game.")))) act("give_up"); }, ".ghost");
    } else if (my && stage === "done") {
      msg = h("strong.mk-turnmsg", T("Build, trade – or end your turn."));
      B(["✔ ", T("End turn")], () => act("end_turn"));
      if ((st.may_build || []).length) B(["🏠 ", T("Build")], myFields, ".ghost");
      more();
    } else {
      msg = h("span.muted", say(tr(T("{0} is playing …"), who(st.turn))));
      more();
    }
    const out = (st.trades || []).find(t => t.from === myId);
    return h("section.card.mk-ctl" + (my ? ".turn" : ""), { style: { "--pc": colorOf(st.turn) } },
      h("div.mk-msg", msg),
      out ? h("div.small.mk-wait", "📨 ", say(tr(T("Waiting for {0} …"), who(out.to))), " ", h("button.btn.small.ghost", { onclick: () => act("cancel", { trade: out.id }) }, T("Withdraw"))) : null,
      btns.length ? h("div.row.wrap.mk-btns", ...btns) : null);
  }
  function result() {
    const ranked = [...st.players].sort((a, b) => (a.place || 99) - (b.place || 99));
    const m = mine();
    if (m.place === 1 && st.complete && !cheered) { cheered = true; confetti(); try { Sound.play("done"); } catch {} }
    const medal = n => ["🥇", "🥈", "🥉"][n - 1] || n + ".";
    const winners = ranked.filter(p => p.place === 1).map(p => p.name).join(" & ");
    const worth = p => (st.worths || {})[p.id] ?? p.worth;
    return h("section.card.center.mk-result",
      h("h2", "🏆 ", C(winners)),
      h("p.muted", T("The richest player wins: Taler + fields + buildings.")),
      h("ol.pk-rank", ...ranked.map(p => h("li" + (p.id === myId ? ".mk-me" : ""), h("span.pj-medal", medal(p.place)), seatIcon(p, 30), C(p.name, "strong.grow"),
        h("span", p.out ? "💸" : mkTaler(worth(p))), p.coins ? h("b.pj-plus", "+" + p.coins + " 🪙") : null))),
      st.complete ? null : h("p.small.muted", T("The game was ended early – ranked as it stood, no coins.")),
      st.coins_on ? null : h("p.small.muted", st.solo ? T("Alone against bots there are no coins.") : T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots.")),
      h("div.row.center", h("button.btn", { onclick: back }, T("Back"))));
  }
  poll();
}

async function dorfmarktView() {
  const box = h("div.mk-live");
  screen("games", box);
  dorfmarktLive(box, S.profile, () => go("games"));
}

async function dorfmarktFamilyCard() {
  const c = S.me && S.me.community, g = c && c.dorfmarkt;
  return h("section.card.quiz-card", h("h2", MK_ICON, " ", mkName()),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("dorfmarkt") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("Buy the shops of the village, build market stands and collect rent – who is the richest at the end? Places 1 to 3 win coins at the family table.")),
         h("div.row.wrap", h("button.btn", { onclick: () => dorfmarktStartDialog(true, () => go("dorfmarkt")) }, "🤖 ", T("Alone against bots")),
           h("button.btn.ghost", { onclick: () => dorfmarktStartDialog(false, () => go("dorfmarkt")) }, "👨‍👩‍👧 ", T("Open a family table")))]);
}
