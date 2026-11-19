// «Snack Rush» – a live snack-stand race (familyquest/snack.py): everybody runs their own snack stand on their own
// device, all get the same customers. Tap a station to start a step (the ring shows how long it takes), tap the done
// food to move it on (to the prep counter or onto the shelf – take it off the grill before it burns!), tap a customer to
// hand over what is on the shelf. Every step costs its ingredients, a served customer pays (and tips when it was fast),
// an angry one walks away without paying – what was made for them goes back onto the shelf. Most money in the till wins.
// snackLive(box, me, back) runs a table (family or alone), snackStartDialog(solo, onStarted) sets the rules.
// The kitchen runs here; the app reports its serves, angry customers and spent money, the others come back with every
// answer. Uses botPicker() from cards.js, withoutBots() / guestInvite() from community.js.
"use strict";

const SN_ICON = "🍔";
const snName = () => I18N.tr(T("Snack Rush"));
const snCoins = list => list.join(" / ") + " 🪙";
const SN_MONEY = "💰";
// the kitchen – the same numbers as in snack.py (FOODS, PRICE, COST, STATIONS, SPOIL, SHELF, SHELF_COLD, TIP)
const SN_FOODS = {
  burger: { steps: [["grill", 4], ["prep", 2]], price: 8, cost: [2, 1], ic: ["🥩", "🍔"], done: "🍔" },
  hotdog: { steps: [["pot", 3], ["prep", 1.5]], price: 6, cost: [2, 1], ic: ["🌭", "🌭"], done: "🌭" },
  fries: { steps: [["fryer", 5], ["prep", 1]], price: 4, cost: [1, 0], ic: ["🥔", "🧂"], done: "🍟" },
  drink: { steps: [["drinks", 3]], price: 3, cost: [1], ic: ["🥤"], done: "🥤" },
  pizza: { steps: [["oven", 6]], price: 7, cost: [3], ic: ["🍕"], done: "🍕" },
  icecream: { steps: [["ice", 2]], price: 4, cost: [1], ic: ["🍦"], done: "🍦" },
};
const SN_FOOD_KEYS = ["burger", "hotdog", "fries", "drink", "pizza", "icecream"];
const SN_FOOD_NAMES = { burger: T("Burger"), hotdog: T("Hot dog"), fries: T("Fries"), drink: T("Drink"), pizza: T("Pizza"), icecream: T("Ice cream") };
const SN_STATIONS = {
  grill: { n: 2, spoil: 4, ic: "🔥", name: T("Grill"), food: "burger" },
  pot: { n: 2, ic: "♨️", name: T("Hot pot"), food: "hotdog" },
  fryer: { n: 2, spoil: 4, ic: "🫕", name: T("Fryer"), food: "fries" },
  drinks: { n: 2, ic: "🚰", name: T("Drinks"), food: "drink" },
  oven: { n: 2, spoil: 5, ic: "🧱", name: T("Oven"), food: "pizza" },
  ice: { n: 2, spoil: 6, ic: "🧊", name: T("Ice machine"), food: "icecream" },
  prep: { n: 3, ic: "🔪", name: T("Prep counter") },
};
const SN = { SHELF: 8, SHELF_COLD: 25, COUNTER: 4, TIP: { 3: 3, 2: 1, 1: 0 } };
const SN_PEOPLE = ["🧒", "👧", "👦", "👩", "👨", "👵", "👴", "🧑", "👱", "🧔"];
const snCost = (food, step, level) => { const c = SN_FOODS[food].cost[step] || 0; return level === "easy" ? Math.floor(c / 2) : c; };
const snFoodCost = (food, level) => SN_FOODS[food].cost.reduce((s, _, k) => s + snCost(food, k, level), 0);
const snStars = (a, p, ts) => { const left = 1 - (ts - a) / p; return left > 0.6 ? 3 : left > 0.3 ? 2 : 1; };
const snPay = (order, stars) => order.reduce((s, f) => s + SN_FOODS[f].price, 0) + (SN.TIP[stars] || 0);
const snMood = left => left > 0.6 ? "😊" : left > 0.35 ? "😐" : left > 0.15 ? "😠" : "😡";
const snClock = s => { s = Math.max(0, Math.ceil(s)); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };

function snackRulesView(r, rewards) {
  r = r || {};
  const mins = { t3: 3, t5: 5, t8: 8 }[r.mode] || 5;
  const items = [
    T("Everybody runs their own snack stand – all stands get the same customers."),
    T("Tap a station to start a step – the ring shows how long it takes. Tap the done food to move it on: to the prep counter or onto the shelf."),
    T("Burger: grill → assemble. Hot dog: pot → into the bun. Fries: fryer → salt. Drink, pizza and ice cream: one step."),
    T("Take food off the grill, the fryer and the oven in time – it burns (the ice cream melts) and goes into the bin."),
    T("Tap a customer (or a food on the shelf) to hand it over. When the whole order is there, the customer pays – fast service gives stars and a tip."),
    T("Every step costs its ingredients. An angry customer walks away without paying – what you made for them goes back onto the shelf for the next one. Food on the shelf gets cold after 25 seconds."),
    I18N.tr(T("The game runs {0} minutes – the most money in the till wins.")).replace("{0}", mins),
    r.limit ? I18N.tr(T("With {0} angry customers you are out.")).replace("{0}", r.limit) : null,
    rewards ? I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", snCoins(rewards)) : null,
    T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."),
  ].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

async function snackStartDialog(solo, onStarted) {
  let r = {};
  try { r = await api("community/snack/rules"); } catch {}
  const sel = (v, list) => h("select", ...list.map(([k, n]) => h("option", { value: k, selected: String(v) === String(k) }, n)));
  const bots = sel(r.bots ?? 0, [0, 1, 2, 3, 4, 5].map(n => [n, String(n)]));
  const level = sel(r.level || "normal", [["easy", T("easy")], ["normal", T("normal")], ["hard", T("hard")]]);
  const mode = sel(r.mode || "t5", [["t3", "⏱️ 3 min"], ["t5", "⏱️ 5 min"], ["t8", "⏱️ 8 min"]]);
  const limit = sel(r.limit ?? 0, [[0, T("off")], [3, "😡 3"], [5, "😡 5"], [8, "😡 8"]]);
  const on = new Set(String(r.foods || SN_FOOD_KEYS.join(",")).split(",").filter(f => SN_FOODS[f]));
  const foods = h("div.sn-foodpick", ...SN_FOOD_KEYS.map(f => h("button.sn-foodchip" + (on.has(f) ? ".on" : ""), { type: "button", "aria-pressed": String(on.has(f)),
    onclick: e => { if (on.has(f) && on.size > 1) on.delete(f); else on.add(f); e.currentTarget.classList.toggle("on", on.has(f)); e.currentTarget.setAttribute("aria-pressed", String(on.has(f))); } },
    h("span.sn-chipic", SN_FOODS[f].done), h("span.small", SN_FOOD_NAMES[f]))));
  const picker = botPicker(1400);
  const speed = picker.el.querySelector(".bot-speed");             // bots work by their level – no reaction time here
  if (speed) speed.remove();
  const rw = r.rewards || [0, 0, 0];
  const coins = solo ? h("p.small.muted", "🪙 ", T("Alone against bots there are no coins."))
    : rw.some(x => x > 0) ? h("p.small.pj-coins", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", snCoins(rw)), h("br"),
      h("span.muted", T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."))) : null;
  const m = modal(h("div.form", h("h2", SN_ICON, " ", T("Snack Rush"), solo ? " – " + I18N.tr(T("Alone")) : ""),
    h("p.small.muted", T("Serve all customers quickly – cook, fry and fill at the same time. Most money in the till wins!")),
    h("div.grid2", h("label.field", T("Duration"), mode), h("label.field", T("Level"), level)),
    h("div.grid2", h("label.field", T("Out after angry customers"), limit), h("label.field", solo ? T("Practice bots") : T("Bots"), bots)),
    h("div.field", h("b", T("Food on the menu")), foods),
    solo ? null : h("p.small.muted", T("1 to 6 players: the family joins on their own devices, guests via QR code.")),
    picker.el,
    coins,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      const body = { solo, bots: +bots.value, level: level.value, mode: mode.value, limit: +limit.value,
        foods: SN_FOOD_KEYS.filter(f => on.has(f)).join(","), bot_ids: picker.ids() };
      try { await api("community/snack/start", { method: "POST", body }); m.close(); onStarted(); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", solo ? T("Play") : T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  withoutBots("snack", bots, picker.el);          // parent area › Games: without bots
}

function snackLive(box, me, back) {
  let st = null, timer = null, alive = true, lastSig = "", cheered = false, busy = false, raf = 0, syncing = false, lastSync = 0;
  let offset = null, bestRtt = 1e9;               // server clock − performance clock (seconds)
  let gameKey = "", cust = new Map(), slots = {}, shelf = [], earned = 0, spent = 0, served = 0, stars = 0, angryN = 0, out = null;
  let pendS = [], pendA = [], els = null;
  const myId = String(me.id);
  box.classList.add("sn-live");
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => { alive = false; clearTimeout(timer); cancelAnimationFrame(raf); box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open"); };
  window.addEventListener("hashchange", stop, { once: true });
  const nowS = () => performance.now() / 1000;
  const gameT = () => (st && offset != null ? nowS() + offset - st.t0 : -9);
  const playing = () => st && st.phase === "play" && st.status !== "done";
  const level = () => (st && st.rules && st.rules.level) || "normal";
  const canAct = () => playing() && st.joined && out == null && gameT() >= 0 && gameT() < (st.duration || 300);
  const snd = k => { try { Sound.play(k); } catch {} };

  function clock(s, t1, t2) {
    if (!s || typeof s.now !== "number") return;
    const rtt = t2 - t1;
    if (rtt <= bestRtt * 1.15 || offset == null) { bestRtt = Math.min(bestRtt, rtt); offset = s.now - (t1 + t2) / 2; }
  }
  const req = async (path, opts) => {
    const t1 = nowS();
    const s = await api("community/snack" + path, opts);
    clock(s, t1, nowS());
    return s;
  };
  const act = async (path, body) => {
    if (busy) return null;
    busy = true;
    try { setState(await req("/" + path, { method: "POST", body: body || {} })); return st; }
    catch (e) { toast(e.message, "bad"); return null; }
    finally { busy = false; draw(true); }
  };
  function setState(s) {
    if (s && !Array.isArray(s.players)) s = null;
    st = s;
    if (!st || st.phase === "lobby" || !st.t0) return;
    const key = st.game + ":" + st.t0;
    if (key !== gameKey) {                          // a new game: an empty kitchen (a reload in the middle keeps the till)
      gameKey = key; cust = new Map(); shelf = []; pendS = []; pendA = []; cheered = false; out = null;
      slots = {};
      for (const f of st.foods || SN_FOOD_KEYS) for (const [s0] of SN_FOODS[f].steps) slots[s0] = slots[s0] || Array(SN_STATIONS[s0].n).fill(null);
      const mine = st.mine || {};
      earned = 0; served = 0; stars = 0; spent = mine.spent || 0;
      for (const v of Object.values(mine.served || {})) { earned += v[2]; served++; stars += v[1]; }
      angryN = (mine.angry || []).length;
      els = null;
    }
    for (const [i, a, p, o] of st.customers || []) {
      if (!cust.has(i)) cust.set(i, { i, a, p, o, got: o.map(() => false), done: false, angry: false });
    }
    if (st.mine) {                                  // the server's word on my customers (after a reload, or a refused serve)
      for (const i of Object.keys(st.mine.served || {})) { const c = cust.get(+i); if (c) c.done = true; }
      for (const i of st.mine.angry || []) {
        const c = cust.get(i);
        if (c && !c.angry) {
          if (c.done) { const v = snPay(c.o, snStars(c.a, c.p, c.doneT || c.a)); earned -= v; served--; }
          c.angry = true; c.done = false;
        }
      }
      angryN = Math.max(angryN, (st.mine.angry || []).length);
    }
    const lim = st.limit || 0;
    if (lim && angryN >= lim && out == null) out = gameT();
  }
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    if (!playing() || !st.joined) {
      try { const s = await req(""); if (!busy) { setState(s); draw(); } } catch {}
    } else if (nowS() - lastSync > 0.9 || pendS.length || pendA.length) sync();
    timer = setTimeout(poll, playing() ? 300 : 1000);
  }
  async function sync() {
    if (syncing || !playing() || !st.joined) return;
    syncing = true; lastSync = nowS();
    const serves = pendS.slice(), angry = pendA.slice();
    try {
      const s = await req("/sync", { method: "POST", body: { t: Math.round(gameT() * 1000) / 1000, serves, angry, spent } });
      pendS = pendS.filter(x => !serves.includes(x)); pendA = pendA.filter(x => !angry.includes(x));
      setState(s); draw();
    } catch {}
    syncing = false;
  }

  // ---------- the kitchen
  function floatText(el, text, cls) {
    if (!el || !els) return;
    const r = el.getBoundingClientRect(), b = box.getBoundingClientRect();
    const f = h("div.sn-float" + (cls ? "." + cls : ""), { "aria-hidden": "true", style: { left: (r.left - b.left + r.width / 2) + "px", top: (r.top - b.top) + "px" } }, text);
    box.append(f);
    setTimeout(() => f.remove(), 1100);
  }
  function bin(el, loss) {                          // into the bin: the money is lost
    snd("trash");
    if (els && els.bin) { els.bin.classList.remove("toss"); void els.bin.offsetWidth; els.bin.classList.add("toss"); }
    floatText(el || (els && els.bin), "🗑️ −" + SN_MONEY + loss, "loss");
  }
  function shake(el) { if (!el) return; el.classList.remove("sn-shake"); void el.offsetWidth; el.classList.add("sn-shake"); snd("wrong"); }
  function tapSlot(station, k, el) {
    if (!canAct()) return;
    const t = gameT(), s = slots[station][k], info = SN_STATIONS[station];
    if (!s) {                                       // an empty place: start the station's food
      if (station === "prep") return shake(el);
      const food = info.food;
      slots[station][k] = { food, step: 0, start: t, dur: SN_FOODS[food].steps[0][1], state: "cook" };
      spent += snCost(food, 0, level());
      snd(station === "drinks" || station === "ice" ? "tap" : "sizzle");
      const c = snCost(food, 0, level());
      if (c) floatText(el, "−" + SN_MONEY + c, "cost");
      return;
    }
    if (s.state === "cook") return shake(el);
    if (s.state === "burnt") {                      // burnt / melted: into the bin
      slots[station][k] = null;
      let loss = 0;
      for (let j = 0; j <= s.step; j++) loss += snCost(s.food, j, level());
      return bin(el, loss);
    }
    // ready: on to the next step, or onto the shelf
    const steps = SN_FOODS[s.food].steps;
    if (s.step + 1 < steps.length) {
      const [next, dur] = steps[s.step + 1];
      const free = slots[next].findIndex(x => !x);
      if (free < 0) { shake(el); return floatText(el, "⏳", "cost"); }
      slots[next][free] = { food: s.food, step: s.step + 1, start: t, dur, state: "cook" };
      slots[station][k] = null;
      const c = snCost(s.food, s.step + 1, level());
      spent += c;
      if (c) floatText(el, "−" + SN_MONEY + c, "cost");
      snd("tap");
      return;
    }
    if (shelf.length >= SN.SHELF) { shake(el); return floatText(el, "⏳", "cost"); }
    shelf.push({ food: s.food, t });
    slots[station][k] = null;
    snd("tap");
  }
  const counter = () => [...cust.values()].filter(c => !c.done && !c.angry && c.a <= gameT()).sort((x, y) => x.i - y.i);
  function give(c, food) {                         // hand one food to a customer: true when it was needed
    const j = c.o.findIndex((f, k) => f === food && !c.got[k]);
    if (j < 0) return false;
    c.got[j] = true;
    return true;
  }
  function finish(c, el) {
    if (!c.got.every(Boolean)) return;
    const t = gameT(), sr = snStars(c.a, c.p, t), v = snPay(c.o, sr);
    c.done = true; c.doneT = t; earned += v; served++; stars += sr;
    pendS.push([c.i, Math.round(t * 1000) / 1000]);
    snd("ding");
    floatText(el, "+" + SN_MONEY + v + " " + "⭐".repeat(sr), "gain");
    sync();
  }
  function tapCustomer(c, el) {
    if (!canAct() || !c) return;
    let n = 0;
    for (let k = 0; k < shelf.length; k++) if (give(c, shelf[k].food)) { shelf.splice(k, 1); k--; n++; }
    if (!n) { shake(el); return floatText(el, "🤷", "cost"); }
    snd("tap");
    finish(c, el);
  }
  function tapShelf(k, el) {
    if (!canAct() || !shelf[k]) return;
    const visible = counter().slice(0, SN.COUNTER);
    const c = visible.find(c => c.o.some((f, j) => f === shelf[k].food && !c.got[j]));
    if (!c) { shake(el); return floatText(el, "🤷", "cost"); }
    give(c, shelf[k].food); shelf.splice(k, 1);
    snd("tap");
    finish(c, els && els.cust[visible.indexOf(c)]);
  }
  function step(t) {                               // the clock of my stand: done, burnt, cold, angry customers
    if (!st || !st.joined) return;
    for (const [station, list] of Object.entries(slots)) {
      list.forEach((s, k) => {
        if (!s) return;
        if (s.state === "cook" && t >= s.start + s.dur) { s.state = "ready"; s.doneAt = s.start + s.dur; if (station !== "prep") snd("right"); }
        const sp = SN_STATIONS[station].spoil;
        if (s.state === "ready" && sp && s.step === 0 && t >= s.doneAt + sp) { s.state = "burnt"; snd("wrong"); }
      });
    }
    for (let k = 0; k < shelf.length; k++) {
      if (t >= shelf[k].t + SN.SHELF_COLD) {
        const f = shelf.splice(k, 1)[0]; k--;
        bin(els && els.shelf, snFoodCost(f.food, level()));
      }
    }
    if (out != null) return;
    for (const c of cust.values()) {
      if (c.done || c.angry || t < c.a + c.p) continue;
      c.angry = true; angryN++; pendA.push(c.i);
      c.o.forEach((f, j) => {                       // what was made for them goes back onto the shelf
        if (!c.got[j]) return;
        if (shelf.length < SN.SHELF) shelf.push({ food: f, t }); else bin(null, snFoodCost(f, level()));
      });
      snd("wrong");
      if (els) floatText(els.counter, "😡", "angry");
      if (navigator.vibrate) try { navigator.vibrate(60); } catch {}
      const lim = st.limit || 0;
      if (lim && angryN >= lim) { out = t; sync(); }
    }
  }

  // ---------- painting (every frame: only text, classes and the rings)
  function build() {
    const others = st.players.filter(p => p.id !== myId);
    els = { cust: [], slot: {}, others: {} };
    els.till = h("strong.sn-till"); els.time = h("span.sn-time"); els.angry = h("span.sn-angry"); els.stars = h("span.sn-stars");
    const bar = h("div.sn-bar", els.till, els.stars, els.angry, els.time);
    els.othersBox = others.length ? h("div.sn-others", ...others.map(p => {
      const e = { till: h("b"), angry: h("span"), el: null };
      e.el = h("div.sn-other", seatIcon(p, 22), C(p.name, "span.sn-oname"), e.till, e.angry);
      els.others[p.id] = e;
      return e.el;
    })) : null;
    els.line = h("span.sn-line");
    els.counter = h("div.sn-counter", ...Array.from({ length: SN.COUNTER }, (_, k) => {
      const b = h("button.sn-cust", { type: "button", onclick: e => tapCustomer(els.cust[k]._c, e.currentTarget) });
      els.cust.push(b);
      return b;
    }));
    els.shelf = h("div.sn-shelf");
    els.bin = h("span.sn-bin", { "aria-hidden": "true" }, "🗑️");
    const shelfRow = h("div.sn-shelfrow", h("span.sn-shelflbl", "🧺"), els.shelf, els.bin);
    const stations = Object.keys(SN_STATIONS).filter(s => slots[s]);
    const card = s => {
      const info = SN_STATIONS[s];
      els.slot[s] = slots[s].map((_, k) => h("button.sn-slot", { type: "button", onpointerdown: e => { e.preventDefault(); tapSlot(s, k, e.currentTarget); },
        onclick: e => { if (e.detail === 0) tapSlot(s, k, e.currentTarget); } }, h("span.sn-ic")));
      return h("div.sn-station" + (s === "prep" ? ".sn-prep" : ""), h("div.sn-sname", info.ic, " ", info.name), h("div.sn-slots", ...els.slot[s]));
    };
    els.kitchen = h("div.sn-kitchen" + (stations.filter(s => s !== "prep").length <= 2 ? ".two" : ""), ...stations.map(card));
    els.over = h("div.sn-over");
    return [bar, els.othersBox, h("div.sn-counterwrap", els.counter, els.line), shelfRow, els.kitchen, els.over];
  }
  function paintSlot(b, s, t, station) {
    const ic = b.firstChild;
    let cls = station === "prep" ? "empty.noadd" : "empty", p = 0, txt = "";
    if (!s) {
      const f = SN_STATIONS[station].food;
      txt = f ? SN_FOODS[f].ic[0] : "·";
    } else if (s.state === "cook") { cls = "cook"; p = Math.min(1, (t - s.start) / s.dur); txt = SN_FOODS[s.food].ic[s.step]; }
    else if (s.state === "ready") {
      const sp = SN_STATIONS[station].spoil, last = s.step + 1 >= SN_FOODS[s.food].steps.length;
      txt = last || s.food === "fries" ? SN_FOODS[s.food].done : SN_FOODS[s.food].ic[s.step];
      if (sp && s.step === 0) { const w = (t - s.doneAt) / sp; cls = w > 0.5 ? "ready.warn" : "ready"; p = 1 - Math.min(1, w); } else { cls = "ready"; p = 1; }
    } else { cls = "burnt"; txt = station === "ice" ? "💧" : "🔥"; }
    const c = "sn-slot " + cls.split(".").join(" ");
    if (b.className !== c) b.className = c;
    b.style.setProperty("--p", p.toFixed(3));
    if (ic.textContent !== txt) ic.textContent = txt;
  }
  function paint(t) {
    if (!els) return;
    const dur = st.duration || 300, lim = st.limit || 0;
    els.till.textContent = SN_MONEY + " " + (earned - spent);
    els.till.classList.toggle("neg", earned - spent < 0);
    els.stars.textContent = "⭐ " + stars;
    els.angry.textContent = "😡 " + angryN + (lim ? "/" + lim : "");
    els.time.textContent = "⏱️ " + snClock(t < 0 ? dur : dur - t);
    for (const p of st.players) {
      const e = els.others[p.id];
      if (!e) continue;
      e.till.textContent = SN_MONEY + (p.till ?? 0);
      e.angry.textContent = (p.out != null ? "💥" : "") + "😡" + (p.angry || 0);
      e.el.classList.toggle("out", p.out != null);
    }
    const list = counter(), vis = list.slice(0, SN.COUNTER);
    els.cust.forEach((b, k) => {
      const c = vis[k];
      b._c = c;
      const key = c ? c.i + ":" + c.got.join() : "";
      if (b._key !== key) {
        b._key = key;
        b.replaceChildren(...(c ? [h("div.sn-order", ...c.o.map((f, j) => h("span" + (c.got[j] ? ".got" : ""), SN_FOODS[f].done))),
          h("div.sn-face", SN_PEOPLE[c.i % SN_PEOPLE.length], h("span.sn-mood")), h("div.sn-pat", h("i"))] : [h("span.sn-free", "·")]));
        b.classList.toggle("free", !c);
      }
      if (c) {
        const left = Math.max(0, 1 - (t - c.a) / c.p);
        const mood = b.querySelector(".sn-mood"), bar = b.querySelector(".sn-pat i");
        const md = snMood(left);
        if (mood.textContent !== md) mood.textContent = md;
        bar.style.width = (left * 100).toFixed(1) + "%";
        bar.className = left > 0.6 ? "ok" : left > 0.3 ? "mid" : "low";
        b.classList.toggle("hurry", left <= 0.15);
      }
    });
    const waiting = list.length - vis.length;
    els.line.textContent = waiting > 0 ? "+" + waiting + " 🚶" : "";
    const key = shelf.map(x => x.food).join();
    if (els.shelf._key !== key) {
      els.shelf._key = key;
      els.shelf.replaceChildren(...shelf.map((x, k) => h("button.sn-item", { type: "button", onclick: e => tapShelf(k, e.currentTarget) }, SN_FOODS[x.food].done)),
        ...(shelf.length ? [] : [h("span.small.muted", T("Ready food lands here"))]));
    }
    [...els.shelf.querySelectorAll(".sn-item")].forEach((b, k) => b.classList.toggle("cold", shelf[k] && t > shelf[k].t + SN.SHELF_COLD - 6));
    for (const [s, bs] of Object.entries(els.slot)) bs.forEach((b, k) => paintSlot(b, slots[s][k], t, s));
    const ov = t < 0 ? String(Math.ceil(-t)) : t < 0.8 ? I18N.tr(T("Go!")) : out != null ? "💥 " + I18N.tr(T("Out!")) : t >= dur ? "⏱️ " + I18N.tr(T("Time is up!")) : "";
    if (els.over.textContent !== ov) { els.over.textContent = ov; els.over.classList.toggle("on", !!ov); }
  }
  function frame() {
    if (!alive || !box.isConnected) return stop();
    raf = requestAnimationFrame(frame);
    if (!playing() || !els) return;
    const t = gameT();
    if (st.joined && t >= 0) step(t);
    paint(t);
  }

  // ---------- the screen
  function draw(force) {
    if (!alive || !box.isConnected) return;
    const sig = JSON.stringify(st && [st.game, st.phase, st.status, st.joined, st.players.map(p => [p.id, p.place]), st.phase === "lobby" ? st.players.length : 0]);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    if (!st) return show(h("section.card.center", h("div.big-ic", SN_ICON), h("h2", T("No game right now")), h("button.btn", { onclick: back }, T("Back"))));
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    const menu = gameMenu({ rules: () => snackRulesView(st.rules, st.coins_on ? st.rewards : null),
      invite: !st.solo && !me.guest && st.status !== "done" ? "snack" : null,
      actions: [{ ic: "⏹", label: T("End the game"), danger: true, hidden: !isHost() || st.status === "done", confirm: T("End the game?"),
        onclick: () => act("end").then(() => { if (!st || st.phase !== "done") { stop(); back(); } }) }],
      onLeave: running ? () => { stop(); back(); } : null });
    const head = h("div.quiz-head.dm-head", h("div.row.head-title", menu, h("h1", SN_ICON, " ", T("Snack Rush"))));
    const host = isHost() && st.status !== "done" && st.phase === "lobby" ? h("div.row.center.host-bar",
      h("button.btn", { onclick: () => act("begin") }, "▶ ", T("Start"))) : null;
    if (st.phase === "done") { els = null; return show(head, result()); }
    if (st.phase === "lobby") {
      els = null;
      if (!st.joined) return show(close, head, h("section.card.center", h("p", T("Play along on this device?")),
        h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join"))), lobbySeats(), host);
      return show(close, head, h("section.card.center", h("h2", T("Waiting for the start …")),
        h("p.muted", T("Everybody joins on their own device.")), lobbySeats(),
        st.coins_on ? h("p.small", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", snCoins(st.rewards))) : null), host);
    }
    if (!st.joined) {
      els = null;
      return show(close, head, h("p.muted.center", T("The game has already started")), h("div.sn-watch", ...[...st.players].sort((a, b) => (b.till || 0) - (a.till || 0))
        .map(p => h("div.sn-other", seatIcon(p, 26), C(p.name, "span.sn-oname"), h("b", SN_MONEY + (p.till || 0)), h("span", "😡" + (p.angry || 0))))));
    }
    if (!els || !els.kitchen || !box.contains(els.kitchen)) show(close, head, ...build());
    else if (els.othersBox) {                       // a player's name / state: only the chips change
      for (const p of st.players) { const e = els.others[p.id]; if (e) e.el.classList.toggle("out", p.out != null); }
    }
  }

  function seatIcon(p, size) {
    return p.bot ? h("span.bot-av", { style: { width: size + "px", height: size + "px", fontSize: (size * 0.6) + "px", background: p.color || null } }, p.emoji || "🤖") : avatarSvg(p.avatar || {}, size);
  }
  function lobbySeats() {
    const free = Array.from({ length: st.bots || 0 }, () => h("div.dm-seat", h("span.bot-av", { style: { width: "30px", height: "30px", fontSize: "18px" } }, "🤖"), h("span.small.muted", T("Bot"))));
    return h("div.dm-seats", ...st.players.map(p => h("div.dm-seat" + (p.id === myId ? ".dm-me" : ""), seatIcon(p, 30), C(p.name, "strong.small.dm-name"))), ...free);
  }
  function result() {
    const ranked = [...st.players].sort((a, b) => (a.place || 99) - (b.place || 99));
    const m = st.players.find(p => p.id === myId) || {};
    if (!cheered && ((m.place === 1 && st.complete && st.players.length > 1) || m.record)) { cheered = true; confetti(); snd("done"); }
    const medal = n => ["🥇", "🥈", "🥉"][n - 1] || n + ".";
    const winners = ranked.filter(p => p.place === 1).map(p => p.name).join(" & ");
    const again = st.solo && st.host === me.id ? h("button.btn", { onclick: async () => {
      try { await api("community/snack/start", { method: "POST", body: { solo: true } }); gameKey = ""; setState(await req("")); draw(true); } catch (e) { toast(e.message, "bad"); }
    } }, "🔄 ", T("Play again")) : null;
    const line = p => h("span.sn-rline", h("b", SN_MONEY + " " + (p.till || 0)), " · 🍽️ " + (p.served || 0) + " · ⭐ " + (p.stars || 0) + " · 😡 " + (p.angry || 0));
    return h("section.card.center.sn-result",
      st.players.length > 1 ? h("h2", "🏆 ", C(winners)) : h("h2", SN_ICON, " ", SN_MONEY + " " + (m.till || 0)),
      st.players.length > 1 ? null : h("p", line(m)),
      m.record ? h("p.sn-record", "🎉 ", T("New personal best!")) : null,
      st.joined && st.best ? h("p.small.muted", "🏆 ", I18N.tr(T("Your best: {0}")).replace("{0}", SN_MONEY + " " + st.best)) : null,
      st.players.length > 1 ? h("ol.pk-rank", ...ranked.map(p => h("li" + (p.id === myId ? ".sn-me" : ""), h("span.pj-medal", medal(p.place)), seatIcon(p, 30),
        h("span.grow.sn-rname", C(p.name, "strong"), h("br"), line(p)), p.coins ? h("b.pj-plus", "+" + p.coins + " 🪙") : null))) : null,
      st.complete ? null : h("p.small.muted", T("The game was ended early – ranked as it stood, no coins.")),
      st.coins_on || st.players.length < 2 ? null : h("p.small.muted", st.solo ? T("Alone against bots there are no coins.") : T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots.")),
      h("div.row.center", again, h("button.btn" + (again ? ".ghost" : ""), { onclick: back }, T("Back"))));
  }
  (async () => { try { setState(await req("")); } catch {} draw(true); poll(); })();
  raf = requestAnimationFrame(frame);
}

async function snackView() {
  const box = h("div.sn-live");
  screen("games", box);
  snackLive(box, S.profile, () => go("games"));
}

async function snackFamilyCard() {
  const c = S.me && S.me.community, g = c && c.snack;
  return h("section.card.quiz-card", h("h2", SN_ICON, " ", T("Snack Rush")),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("snack") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("Run your own snack stand: grill, fry and fill at the same time and serve every customer before they get angry. Everybody gets the same customers – most money in the till wins.")),
         gameStartRow(() => snackStartDialog(true, () => go("snack")), () => snackStartDialog(false, () => go("snack")))]);
}
