// ---------------------------------------------------------------- 🎲 Games: the list of games, custom games, game battery, party mode, prices, photo sets, running games
// A part of the parent area (parent.js): loaded after it, before boot() runs (eltern.html).
"use strict";

// ---------------------------------------------------------------- the games of the app (parent area › Games)
const GAME_LIST = [["quiz", "🎯", T("Family quiz")], ["bingo", "🎱", "Bingo"], ["song", "🎵", T("Guess the song")], ["tschau", "🂡", "Tschau Sepp"], ["karussell", "🎠", T("Card Carousel")], ["domino", "🁫", "Domino"], ["paarjagd", "🧠", T("Pair Hunt")], ["werbinich", "🎭", T("Who am I?")],
    ["kartenlauf", "🏁", T("Card Race")], ["stadtland", "🏙️", T("City, Country, River")], ["zeichnen", "🎨", T("Draw & Guess")], ["wuerfel", "🎲", T("Five Dice")], ["heimwaerts", "🏠", T("Homeward")], ["jump", "🦘", "Jump"], ["sternlauf", "🌠", T("Star Runner")], ["snack", "🍔", T("Snack Rush")], ["verkehr", "🚦", T("Traffic Cadet")], ["klatsch", "👏", T("Clap the Beat")], ["verboten", "🚫", T("Forbidden Words")], ["jass", "♣️", T("Jass")], ["werwolf", "🐺", T("Werewolves")], ["schach", "♟️", T("Chess")], ["dorfmarkt", "🏘️", T("Village Market")], ["escape", "🗝️", T("Escape Room")], ["stempeljagd", "🏛️", T("Beat the Bureaucracy")], ["poker", "🃏", "Texas Hold'em"], ["ttt", "⭕", T("Tic-Tac-Toe")], ["sudoku", "🔢", T("Sudoku")], ["patience", "🃏", T("Patience")], ["cube", "🧊", T("Cube solver")],
    ["pingpong", "🏓", T("Ping-Pong")], ["slots", "🎰", T("One-armed bandit")]];
GAME_LIST.splice(GAME_LIST.findIndex(g => g[0] === "verkehr") + 1, 0, ["langstrecke", "🏎️", T("24h Endurance")]);
GAME_LIST.push(["adventuregame", "🗝️", T("Adventure games")]);
// 🛠️ Custom games: the games with the family's own content (quizzes, photo sets, adventure games) – on top of the page
const CUSTOM_GAMES = ["quiz", "paarjagd", "adventuregame"];
// the built-in games in the groups of the children's games page (kid.js gamesView, minigames.js «Game corner»)
const GAME_GROUPS = [["night", "🎲", T("For a game night"), ["tschau", "karussell", "domino", "jass", "poker", "dorfmarkt", "heimwaerts", "langstrecke", "kartenlauf",
    "werwolf", "escape", "stempeljagd", "werbinich", "verboten", "zeichnen", "stadtland", "song", "bingo", "schach"]],
  ["quick", "⚡", T("Quick games for in between"), ["wuerfel", "jump", "klatsch", "sternlauf", "snack", "verkehr"]],
  ["corner", "🕹️", T("Game corner"), ["ttt", "pingpong", "sudoku", "patience", "slots", "cube"]]];
const FREE_GAMES = new Set(["adventuregame"]);             // no price, no rent (services.py FREE_GAMES)

// per game: active / active without bots (only games with bots) / inactive – and for whom (everybody or chosen children)
// ---------------------------------------------------------------- game battery and party mode (familyquest/battery.py)
const UNL_CHOICES = () => [["off", T("Off")], ["forever", T("Permanent")], ["day", T("For 1 day")], ["week", T("For 1 week")], ["month", T("For 1 month")]];
const unlRunning = v => v && v !== "forever" && new Date(v.replace(" ", "T")) > new Date();

/** The values of the game battery – the family default (`own` null) or one child's own values («as the family»). */
function batteryForm(values, own, onSave, ...more) {
  const fam = values, kid = own != null;
  const has = k => kid && Object.prototype.hasOwnProperty.call(own, k);
  const num = (k, min, max) => {
    const inp = h("input", { type: "number", min, max, step: 1, inputmode: "numeric", value: kid ? (has(k) ? own[k] : "") : fam[k],
      placeholder: kid ? I18N.tr(T("as family")) + " (" + fam[k] + ")" : "",
      onchange: () => onSave({ [k]: inp.value === "" ? (kid ? null : fam[k]) : Math.max(min, Math.min(max, Math.round(+inp.value || 0))) }) });
    return inp;
  };
  const on = kid ? h("select", { onchange: () => onSave({ on: on.value === "" ? null : on.value === "1" }) },
      h("option", { value: "", selected: !has("on") }, I18N.tr(T("as family")) + " (" + I18N.tr(fam.on ? T("On") : T("Off")) + ")"),
      h("option", { value: "1", selected: has("on") && own.on }, T("On")), h("option", { value: "0", selected: has("on") && !own.on }, T("Off")))
    : h("input", { type: "checkbox", checked: fam.on, onchange: () => onSave({ on: on.checked }) });
  const cur = kid ? (has("unlimited") ? own.unlimited : null) : fam.unlimited;
  const running = unlRunning(cur);
  const unl = h("select", { onchange: () => onSave({ unlimited: unl.value }) },
    kid ? h("option", { value: "family", selected: !has("unlimited") }, T("as family")) : null,
    running ? h("option", { value: "keep", selected: true }, "∞ " + untilWhen(cur)) : null,
    ...UNL_CHOICES().map(([v, n]) => h("option", { value: v, selected: !running && (v === "forever" ? cur === "forever" : v === "off" && (kid ? has("unlimited") && cur === "" : !cur)) }, n)));
  return h("div.form.bat-form",
    kid ? h("label.field", h("span", "🔋 ", T("Game battery")), on) : h("label.check", on, h("span", "🔋 ", T("Game battery on – starting a game costs a segment"))),
    // the small fields side by side (two per row on a phone)
    h("div.field-row", h("label.field", h("span", T("Capacity (segments)"), fieldInfo(T("1 to 20 – starts full."))), num("cap", 1, 20)),
      h("label.field", h("span", "⚡ ", T("Recharging costs (coins)"), fieldInfo(T("0 = recharging is free."))), num("cost", 0, 10000)),
      h("label.field", h("span", "∞ ", T("Unlimited energy")), unl,
        running || cur === "forever" ? h("button.btn.small.ghost", { type: "button", onclick: () => onSave({ unlimited: kid ? "family" : "off" }) }, "⏹ ", T("End")) : null),
      ...more));
}

/** Parent area › Games: the family default of the game battery, the daily goal, every child's charge now. */
function batterySettingsCard() {
  const box = h("div.bat-settings");
  const fold = setFold("games.battery", ["🔋 ", T("Game battery")], box);
  fold.querySelector(".set-head > h2").dataset.ik = "Game battery";
  const draw = d => {
    const save = async v => { try { draw(await call("parent/battery", { method: "PUT", body: v })); toast(T("Saved"), "good"); } catch {} };
    const fam = d.family;
    const goal = h("select", { onchange: () => save({ goal: goal.value }) }, ...[["off", T("Nothing")], ["full", T("Battery full")], ["plus", T("Extra segments")]]
      .map(([v, n]) => h("option", { value: v, selected: fam.goal === v }, n)));
    const plus = h("input", { type: "number", min: 1, max: 20, step: 1, value: fam.goal_plus, inputmode: "numeric", onchange: () => save({ goal_plus: +plus.value }) });
    fold.querySelector(".set-status").textContent = fam.unlimited ? "∞ " + I18N.tr(T("Unlimited energy"))
      : I18N.tr(T("Segments: {0}")).replace("{0}", fam.cap) + (fam.cost ? " · ⚡ " + fam.cost + " 🪙" : "");
    box.replaceChildren(
      batteryForm(fam, null, save, h("label.field", h("span", "🎯 ", T("Daily goal reached")), goal), fam.goal === "plus" ? h("label.field", h("span", T("Extra segments")), plus) : null),
      h("ul.list.bat-kids", ...d.kids.map(k => h("li.row", k.state ? batteryIcon(k.state) : null, C(k.name, "strong.grow"),
        h("span.small.muted", k.state && k.state.free ? (k.state.party ? "🎉 " : "∞ ") + (k.state.until ? untilWhen(k.state.until) : "") : k.state ? k.state.charge + " / " + k.state.cap : ""),
        k.state && !k.state.free && k.state.charge < k.state.cap ? h("button.btn.small.ghost", { onclick: async () => { draw(await call(`parent/battery/${k.id}/recharge`, { method: "POST" })); toast(T("Battery recharged"), "good"); } }, "🎁 ", T("Recharge")) : null))));
  };
  call("parent/battery").then(draw).catch(() => {});
  return fold;
}

/** Profile dialog of a child: its own battery values (empty = as the family). */
function kidBatteryBox(pid) {
  const box = h("div.form.lim-box", h("h3", { "data-ik": "Game battery" }, "🔋 ", T("Game battery")), h("p.small.muted", "…"));
  const draw = d => {
    const k = d.kids.find(x => x.id === pid);
    if (!k) return box.replaceChildren();
    const save = async v => { try { draw(await call(`parent/battery/${pid}`, { method: "PUT", body: v })); toast(T("Saved"), "good"); } catch {} };
    box.replaceChildren(box.firstChild,
      k.state ? h("div.row", batteryIcon(k.state, true), h("span.grow", k.state.party ? "🎉 " + I18N.tr(T("Party mode")) : k.state.free ? "∞" + (k.state.until ? " " + untilWhen(k.state.until) : "") : k.state.charge + " / " + k.state.cap),
        !k.state.free && k.state.charge < k.state.cap ? h("button.btn.small.ghost", { type: "button", onclick: async () => { draw(await call(`parent/battery/${pid}/recharge`, { method: "POST" })); } }, "🎁 ", T("Recharge")) : null) : null,
      batteryForm(d.family, k.own, save));
  };
  call("parent/battery").then(draw).catch(() => box.replaceChildren());
  return box;
}

/** 🎉 Party mode: a switch with a chooser – for whom, what, how long (Games page and overview). */
function partyCard() {
  const box = h("section.card.sec.party-card");
  const draw = async () => {
    let p = null, kids = [];
    try { [p, kids] = await Promise.all([call("parent/party"), call("parent/profiles").then(l => l.filter(x => x.role === "kid"))]); } catch { return; }
    const sw = h("input.party-switch", { type: "checkbox", role: "switch", checked: !!p, "aria-label": T("Party mode"),
      onchange: async () => {
        if (sw.checked) { sw.checked = false; return partyDialog(kids, draw); }
        if (!(await confirmDialog(I18N.tr(T("End the party mode?"))))) { sw.checked = true; return; }
        await call("parent/party", { method: "DELETE" }); toast(T("Party mode ended"), "good"); draw();
      } });
    const who = p ? (p.kids === "all" ? I18N.tr(T("all children")) : p.kids.map(id => (kids.find(k => k.id === id) || {}).name || "?").join(", ")) : "";
    const what = p ? [p.unlock ? T("all games open") : null, p.battery ? T("starting is free") : null, p.limits ? T("no game time limit") : null].filter(Boolean).map(t => I18N.tr(t)).join(" · ") : "";
    box.classList.toggle("on", !!p);
    box.replaceChildren(h("div.row", h("span.big-ic", "🎉"), h("div.grow", h("h2", { "data-ik": "Party mode" }, T("Party mode")),
        p ? h("div.small", h("b", p.until ? untilWhen(p.until) : I18N.tr(T("until switched off"))), " · ", C(who), what ? h("div.small.muted", what) : null) : null),
      h("label.switch-wrap", sw, h("span.switch-ui"))));
  };
  draw();
  return box;
}

function partyDialog(kids, after) {
  const all = h("input", { type: "radio", name: "pk", checked: true }), some = h("input", { type: "radio", name: "pk" });
  const picks = kids.map(k => h("label.check", h("input", { type: "checkbox", value: k.id, checked: true }), C(k.name)));
  const pickRow = h("div.row", { hidden: true }, ...picks);
  all.onchange = some.onchange = () => { pickRow.hidden = !some.checked; };
  const chk = (label, hint) => { const i = h("input", { type: "checkbox", checked: true }); return [i, h("label.check", i, h("span", label, hint ? h("span.small.muted", " – ", hint) : null))]; };
  const [unlock, unlockL] = chk("🔓 " + I18N.tr(T("Unlock all games")), T("price, rent and «inactive» do not count"));
  const [batt, battL] = chk("🔋 " + I18N.tr(T("Unlimited battery")), null);
  const [lim, limL] = chk("⏱️ " + I18N.tr(T("Also lift limits")), T("daily game time, game block times and the OfflineTime game lock – internet and learning stay as they are"));
  let dur = "forever";
  const durs = h("div.pin-kind.party-durs");
  const drawDur = () => durs.replaceChildren(...[["forever", T("Until switched off")], ["1h", "1 h"], ["3h", "3 h"], ["midnight", T("Until midnight")], ["day", T("1 day")]]
    .map(([v, n]) => h("button.btn.small" + (dur === v ? "" : ".ghost"), { type: "button", "aria-pressed": String(dur === v), onclick: () => { dur = v; drawDur(); } }, n)));
  drawDur();
  const m = modal(h("div.form.party-dialog", h("h2", "🎉 ", T("Party mode")),
    h("h3", T("For whom")), h("div.row", h("label.check", all, T("All children")), h("label.check", some, T("Chosen children"))), pickRow,
    h("h3", T("What")), unlockL, battL, limL,
    h("h3", T("How long")), durs,
    h("div.row", h("button.btn", { onclick: async () => {
      const body = { kids: all.checked ? "all" : picks.map(l => l.querySelector("input")).filter(i => i.checked).map(i => +i.value),
        unlock: unlock.checked, battery: batt.checked, limits: lim.checked, for: dur };
      try { await call("parent/party", { method: "POST", body }); } catch { return; }
      m.close(); confetti(); toast(T("Party mode on – have fun!"), "good"); after();
    } }, "🎉 ", T("Start the party")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
}

function gameAccess(kids, data) {
  let acc = data.access, returns = data.slots_returns || {};
  const botGames = new Set(data.bot_games || []), bars = {}, chipRows = {};
  const save = async k => {
    try { const r = await call("parent/games", { method: "PUT", body: { access: k ? { [k]: acc[k] } : acc } }); acc = r.access; returns = r.slots_returns || returns; toast(T("Saved"), "good"); } catch {}
    new Set([...Object.keys(bars), ...Object.keys(chipRows)]).forEach(draw);
  };
  // the folded row of a game shows its settings at a glance: status, who, price / rent
  const drawChips = k => {
    const a = acc[k] || { mode: "all", profiles: [], bots: true }, row = chipRows[k];
    if (!row) return;
    const state = a.mode === "off" ? "off" : a.bots === false ? "nobots" : "on";
    const per = I18N.tr({ day: T("Day"), week: T("Week"), month: T("Month") }[a.period || "week"] || T("Week"));
    row.replaceChildren(
      state === "off" ? chip("✕ " + I18N.tr(T("Inactive")), "bad") : chip(state === "nobots" ? "🚫 " + I18N.tr(T("Active without bots")) : "✓ " + I18N.tr(T("Active")), "good"),
      state !== "off" && a.mode === "some" ? chip("👥 " + I18N.tr(T("Only chosen children"))) : null,
      state === "off" || FREE_GAMES.has(k) ? null : a.price > 0 || a.rent > 0
        ? null : chip(I18N.tr(T("Free"))),
      state !== "off" && a.price > 0 ? chip("🪙 " + fmt(a.price)) : null,
      state !== "off" && a.rent > 0 ? chip("🔁 " + fmt(a.rent) + " 🪙/" + per) : null);
  };
  const draw = k => {
    drawChips(k);
    const a = acc[k] || { mode: "all", profiles: [], bots: true }, bar = bars[k];
    if (!bar) return;
    const state = a.mode === "off" ? "off" : a.bots === false ? "nobots" : "on";
    const set = v => { acc[k] = v === "off" ? { ...a, mode: "off" } : { ...a, mode: a.mode === "off" ? "all" : a.mode, bots: v === "on" }; save(k); };
    bar.classList.toggle("off", state === "off");                  // the section is dimmed (parent.css)
    bar.replaceChildren(...[
      h("div.pin-kind.game-state", ...[["on", "✓ ", T("Active")], botGames.has(k) ? ["nobots", "🚫 ", T("Active without bots")] : null, ["off", "✕ ", T("Inactive")]].filter(Boolean)
        .map(([v, ic, n]) => h("button.btn.small" + (state === v ? (v === "off" ? ".bad" : "") : ".ghost"), { "aria-pressed": String(state === v), onclick: () => set(v) }, ic, n)),
        botGames.has(k) ? fieldInfo(T("No «alone against bots», no bots at the table, no games against the app – only people play. Parents are not bound."), { title: T("Active without bots") }) : null),
      state === "off" ? null : h("div.pin-kind", ...[["all", T("For everybody")], ["some", T("Only chosen children")]].map(([m, n]) =>
        h("button.btn.small" + (a.mode === m ? "" : ".ghost"), { onclick: () => { acc[k] = { ...a, mode: m }; save(k); } }, n))),
      state !== "off" && a.mode === "some" ? h("div.row.game-kids", ...kids.map(kid => h("label.check", h("input", { type: "checkbox", checked: a.profiles.includes(kid.id),
        onchange: e => { const ids = new Set(a.profiles); e.target.checked ? ids.add(kid.id) : ids.delete(kid.id); acc[k] = { ...a, profiles: [...ids] }; save(k); } }), C(kid.name)))) : null,
      state === "off" || FREE_GAMES.has(k) ? null : gamePriceBox(k, a, v => { acc[k] = { ...a, ...v }; save(k); }, returns)].filter(Boolean));
  };
  return {
    bar: k => { if (!bars[k]) { bars[k] = h("div.game-status"); setTimeout(() => draw(k)); } return bars[k]; },
    chips: k => { if (!chipRows[k]) { chipRows[k] = h("span.game-chips"); drawChips(k); } return chipRows[k]; },
    allTo: mode => { for (const [k] of GAME_LIST) if (k in acc) acc[k] = { ...(acc[k] || { profiles: [] }), mode }; return save(null); },
  };
}

// what a child pays for a game (familyquest/gamepasses.py): buy once, or rent per day / week / month – 0 and 0 = free;
// the fields show the defaults (quick games 100 a week, game corner 20 a day) – saving stores them as shown; free tries;
// the one-armed bandit also gets its luck (1–10, what comes back on average). Parents always play for free.
function gamePriceBox(k, a, set, returns) {
  const num = (v, max = 100000) => Math.max(0, Math.min(max, Math.round(+v || 0)));
  const price = h("input", { type: "number", min: 0, max: 100000, step: 1, inputmode: "numeric", value: a.price || 0,
    onchange: () => set({ price: num(price.value) }) });
  const rent = h("input", { type: "number", min: 0, max: 100000, step: 1, inputmode: "numeric", value: a.rent || 0,
    oninput: () => periods.querySelectorAll("button").forEach(b => { b.disabled = !num(rent.value); }),
    onchange: () => set({ rent: num(rent.value) }) });
  const periods = h("div.pin-kind.gp-periods", ...[["day", T("Day")], ["week", T("Week")], ["month", T("Month")]].map(([v, n]) =>
    h("button.btn.small" + ((a.period || "week") === v ? "" : ".ghost"), { disabled: !(a.rent > 0), "aria-pressed": String((a.period || "week") === v),
      onclick: () => set({ period: v }) }, n)));
  // free tries before buying / renting (default 1) – only with a price or a rent
  const preview = h("input.gp-preview", { type: "number", min: 0, max: 20, step: 1, inputmode: "numeric", value: a.preview ?? 1,
    onchange: () => set({ preview: num(preview.value, 20) }) });
  let luck = null;
  if (k === "slots") {
    const pct = v => I18N.tr(T("≈ {0} % comes back on average")).replace("{0}", returns[v] ?? "?");
    const hint = h("span.hint", pct(a.luck || 5));          // the live value stays visible
    const range = h("input.gp-luck", { type: "range", min: 1, max: 10, step: 1, value: a.luck || 5,
      oninput: () => { hint.textContent = pct(range.value); val.textContent = range.value; }, onchange: () => set({ luck: +range.value }) });
    const val = h("b", String(a.luck || 5));
    luck = h("label.field", h("span", "🍀 ", T("Win chance"), " ", val, " / 10",
      fieldInfo(T("5 = like a typical casino machine. Higher: better odds for the children, lower: worse."))), range, hint);
  }
  // side by side: price · free tries · rent with its period (the rent spans two columns, so day / week / month stay next to it)
  rent.setAttribute("aria-label", T("Rent price (coins)"));
  return h("div.gp-box",
    h("div.field-row",
      h("label.field", h("span", "🪙 ", T("Price for children (coins)"),
        fieldInfo(T("0 = free. Bought once, the game stays the child's for good – also when you change the price."), T("With a price the children buy or rent the game in the shop. Parents always play for free."))), price),
      h("label.field", h("span", "🎁 ", T("Free tries before buying"),
        fieldInfo(T("How often a child may play the game for free before buying or renting it. Only matters with a price or a rent."))), preview),
      h("div.field.span2", h("span", "🔁 ", T("Rent price (coins)"),
        fieldInfo(T("0 = no renting. Renting opens the game for one day, week or month; renting again adds the time."))), h("div.gp-rent", rent, periods))),
    luck);
}

// photo sets of the pairs game and the Paarjagd (parent area › Games › Custom games › Pair Hunt): the list of the sets,
// «+ New» starts with a preset (an empty set with a name), «📥 Import» takes photos or a ZIP file, ⬇️ a set as ZIP
const PHOTO_PRESETS = () => [["👨‍👩‍👧", T("Family")], ["🐾", T("Pets")], ["🏖️", T("Holidays")], ["🎂", T("Birthdays")], ["👵", T("Grandparents")], ["🏠", T("Our home")]];
async function photoSets(onCount = null) {
  let d = { sets: [] };
  try { d = await call("parent/memory"); } catch {}
  const setsBox = h("div.mm-sets");
  const save = async (quiet = false) => {
    for (const st of d.sets) if (!st.name.trim()) {               // a set without a name gets a free «Photos n»
      let n = 1; const taken = new Set(d.sets.map(x => x.name));
      while (taken.has(I18N.tr(T("Photos {0}")).replace("{0}", n))) n++;
      st.name = I18N.tr(T("Photos {0}")).replace("{0}", n);
    }
    try {
      const r = await call("parent/memory", { method: "PUT", body: { sets: d.sets } });
      // keep the objects on screen (an upload still running adds to them), only take over what the server decided
      r.sets.forEach((x, i) => { if (d.sets[i]) Object.assign(d.sets[i], { id: x.id, name: x.name }); });
      drawSets(); if (!quiet) toast(T("Saved"), "good");
    }
    catch (e) { toast(e.message, "bad"); }
  };
  const addTo = st => async names => { st.photos.push(...names.filter(n => !st.photos.includes(n))); drawSets(); await save(true); toast(I18N.tr(T("{0} photos added")).replace("{0}", names.length), "good"); };
  const drawSets = () => {
    if (onCount) onCount(d.sets.length);
    setsBox.replaceChildren(...(d.sets.length ? [] : [h("p.small.muted.sb-empty", T("Nothing here yet – start with «+ New»."))]), ...d.sets.map((st, i) => h("div.card.qe",
    h("div.row", h("input.grow", { type: "text", maxlength: 60, value: st.name, placeholder: I18N.tr(T("e.g. Our holidays")), oninput: e => { st.name = e.target.value; } }),
      st.id && st.photos.length ? h("button.icon-btn", { title: T("Export as ZIP file"), onclick: () => downloadApi(`parent/memory/sets/${st.id}/export`, "family-quest-photos.zip") }, "⬇️") : null,
      h("button.icon-btn", { title: T("Delete"), onclick: async () => { if ((await confirmDialog(I18N.tr(T("Delete the photo set «{0}»?")).replace("{0}", st.name || "–")))) { d.sets.splice(i, 1); drawSets(); save(true); } } }, "🗑️")),
    h("div.mm-thumbs", ...st.photos.map((ph, j) => h("div.mm-thumb", h("img", { src: memPhotoUrl(ph), alt: "", loading: "lazy" }),
      h("button", { title: T("Remove photo"), onclick: () => { st.photos.splice(j, 1); drawSets(); } }, "✕")))),
    h("div.row.wrap",
      h("button.btn.ghost.small", { onclick: () => Photos.pick(true, addTo(st)) }, "📷 ", T("Add photos"))),
    h("p.small.muted", I18N.tr(T("Photos: {0}")).replace("{0}", st.photos.length), st.photos.length < 3 ? [" – ", T("at least 3 photos for a game")] : null))));
  };
  const free = name => { const taken = new Set(d.sets.map(x => x.name)); let n = name, i = 2; while (taken.has(n)) n = name + " " + i++; return n; };
  const add = async (name, photos = []) => {
    if (d.sets.length >= 20) return toast(T("At most 20 photo sets – delete one first"), "bad");
    d.sets.unshift({ name: free(name), photos }); drawSets(); await save(true);
    toast(photos.length ? I18N.tr(T("{0} photos added")).replace("{0}", photos.length) : T("Photo set added – now add photos"), "good");
  };
  // «+ New»: a preset (an empty set with its name) or an empty set without a name
  const newDialog = () => {
    const tile = (ic, name, go) => h("button.mm-preset", { onclick: () => { m.close(); go(); } }, h("span.big-ic", ic), h("strong", name));
    const m = modal(h("div.form", h("h2", "🧠 ", T("New photo set")),
      h("div.mm-presets", tile("📄", T("Empty set"), () => { d.sets.unshift({ name: "", photos: [] }); drawSets(); setsBox.querySelector("input").focus(); }),
        ...PHOTO_PRESETS().map(([ic, n]) => tile(ic, n, () => add(ic + " " + I18N.tr(n))))),
      h("div.row", h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))), { wide: true });
  };
  // «📥 Import»: one or several photos at once – becomes a new set
  const importDialog = () => pickFiles({ accept: "image/*", multiple: true }, async files => {
    const names = [...new Set(await Photos.uploadAll(files))].slice(0, 40);
    if (names.length) await add(I18N.tr(T("Photos {0}")).replace("{0}", d.sets.length + 1), names);
  });
  drawSets();
  return { newDialog, importDialog, el: h("div.mm-box",
    setsBox,
    h("div.row", h("button.btn", { onclick: () => save() }, "💾 ", T("Save")))) };
}

// ---------------------------------------------------------------- running games: end one or all (familyquest/running.py)
function runningGamesBox() {
  const box = h("div.run-group");
  const draw = list => {
    if (!list.length) return box.replaceChildren();
    const endOne = async g => {
      if (!(await confirmDialog(I18N.tr(T("End «{0}» now?")).replace("{0}", I18N.tr(g.title))))) return;
      try { draw((await call("parent/games/end", { method: "POST", body: { key: g.key } })).running); toast(T("Game ended"), "good"); render(); } catch {}
    };
    const endAll = async () => {
      if (!(await confirmDialog(I18N.tr(T("End all {0} running games?")).replace("{0}", list.length)))) return;
      try { draw((await call("parent/games/end", { method: "POST", body: { all: true } })).running); toast(T("All games ended"), "good"); render(); } catch {}
    };
    box.replaceChildren(setGroup("Running games", "⏹", T("Running games"),
      list.length > 1 ? h("button.btn.small.ghost", { onclick: endAll }, "⏹ ", T("End all")) : null),
      h("section.card.sec.run-box", h("div.run-list", ...list.map(g => h("div.row.run-item",
        h("span.run-ic", g.icon), h("div.grow", h("strong", I18N.tr(g.title)), h("br"),
          h("span.small.muted", [g.solo ? T("alone against bots") : T("family table"), g.host ? " · " + g.host : "",
            " · ", I18N.tr(T("Players: {0}")).replace("{0}", g.players), g.status === "lobby" ? [" · ", T("waiting to start")] : null,
            g.status === "paused" ? [" · ⏸ ", T("paused")] : null])),
        h("button.btn.small.ghost", { onclick: () => endOne(g) }, "⏹ ", T("End")))))));
  };
  call("parent/games/running").then(draw).catch(() => {});
  return box;
}

// ---------------------------------------------------------------- games: per game active / without bots / inactive, start, coins, running tables
async function gamesView(main) {
  const me = P.meta.me;
  const [s, profiles, data] = await Promise.all([call("parent/settings"), call("parent/profiles"), call("parent/games")]);
  const access = gameAccess(profiles.filter(p => p.role === "kid"), data);
  // every game folded, always (the page is long on phones; a search opens the games found) – a game running now
  // shows «● running now»; inside: first what to play, then – set apart – its settings (status, coins)
  const runningNow = new Set((await call("parent/games/running").catch(() => [])).map(g => g.game));
  const gsec = (k, title, actions, ...content) => {
    const flat = content.flat(Infinity).filter(x => x != null && x !== false);
    const settings = flat.filter(x => x.classList && x.classList.contains("pj-rewards")), play = flat.filter(x => !settings.includes(x));
    return h("details.card.sec.game-sec", { "data-game": k },
      h("summary.sec-head", h("h2", { "data-ik": (GAME_LIST.find(g => g[0] === k) || [])[2] }, title, runningNow.has(k) ? h("span.chip.run-chip", "● ", T("running now")) : null), h("div.head-actions", ...[].concat(actions)), access.chips(k)),
      play.length ? h("div.game-play", ...play) : null,
      h("div.game-settings", h("div.small.muted.game-settings-h", "⚙️ ", T("Settings")), access.bar(k), ...settings));
  };
  // 🛠️ Custom games: the same structure for each – what it is and how many, «📥 Import» and «+ New» (templates first),
  // the own content (quizzes, photo sets, adventure games), then the settings (status, coins)
  // the same order everywhere: play (family table / alone / ↗ in the app), then the own content under its title with
  // «+ New» (and «📥 Import» where it makes sense) next to that title, then the settings
  const csec = (k, head, contentTitle, ...settings) => {
    const [, ic, name] = GAME_LIST.find(g => g[0] === k);
    const count = h("span.chip.cg-count", "…"), actions = h("div.row.wrap.cg-actions"), list = h("div.cg-list");
    const play = h("div.row.wrap.cg-play-btns"), playRow = h("div.game-play.cg-play", play, head ? Object.assign(head, { className: head.className + " cg-app" }) : null);
    const el = h("details.card.sec.game-sec.cg-sec", { "data-game": k },
      h("summary.sec-head", h("h2", { "data-ik": name }, ic, " ", I18N.tr(name), " ", count, runningNow.has(k) ? h("span.chip.run-chip", "● ", T("running now")) : null),
        access.chips(k)),
      playRow,
      h("div.row.wrap.cg-content-head", h("h3.cg-sub.grow", { "data-ik": "cg." + k }, contentTitle), actions), list,
      h("div.game-settings", h("div.small.muted.game-settings-h", "⚙️ ", T("Settings")), access.bar(k), ...settings));
    return { el, actions, list, play, count: n => { count.textContent = String(n); } };
  };
  const live = h("div"), quizzes = h("div"), bingo = h("div"), poker = h("div"), cardBoxes = { tschau: h("div"), karussell: h("div") }, domino = h("div"), paarjagd = h("div"), werbinich = h("div"), kartenlauf = h("div"), stadtland = h("div"), zeichnen = h("div"), wuerfel = h("div"), heimwaerts = h("div"), jump = h("div"), sternlauf = h("div"), snack = h("div"), verkehr = h("div"), klatsch = h("div"), verboten = h("div"), jass = h("div"), werwolf = h("div"), schach = h("div"), dorfmarkt = h("div"), escape = h("div"), stempeljagd = h("div");
  const langstrecke = h("div");
  const showLive = async () => {
    let st = null; try { st = await call("community/quiz"); } catch {}
    if (!st || st.status === "done") return live.replaceChildren();
    // a running quiz is a card here – it opens full screen only on «Open» (✕ comes back to the card, not into the quiz again)
    const open = () => {
      const box = h("div.quiz-live");
      live.replaceChildren(sectionAdd("🎯 " + I18N.tr(T("Running quiz")), appBtn("quiz"), box));
      quizLive(box, me, () => showLive());
    };
    const end = async () => {
      if (!(await confirmDialog(I18N.tr(T("End the running quiz?"))))) return;
      try { await call("community/quiz/abort", { method: "POST" }); } catch {}
      showLive();
    };
    live.replaceChildren(sectionAdd("🎯 " + I18N.tr(T("Running quiz")), appBtn("quiz"),
      h("div.row.wrap", C("«" + quizTitle(st.title, st.langs) + "»", "strong.grow"),
        h("span.small.muted", I18N.tr((st.players || []).length === 1 ? T("1 playing") : T("{0} playing")).replace("{0}", (st.players || []).length)),
        h("button.btn.small", { onclick: open }, "▶ ", T("Open")),
        h("button.btn.small.ghost", { onclick: end }, "⏹ ", T("End")))));
  };
  // bingo: start it here, lead and play in the full-screen view
  const showBingo = async () => {
    let b = null; try { b = await call("community/bingo"); } catch {}
    const open = () => { const box = h("div.bingo-live"); bingo.replaceChildren(box); bingoLive(box, me, () => render()); };
    bingo.replaceChildren(gsec("bingo", "🎱 Bingo", appBtn("bingo"), b && b.status !== "done"
      ? h("button.btn", { onclick: open }, b.card ? T("Back to the game") : T("Join"))
      : [h("button.btn", { onclick: () => bingoStartDialog(open) }, "▶ ", T("Start bingo"))]));
  };
  const showPoker = async () => {
    let g = null; try { g = await call("community/poker"); } catch {}
    const open = () => { const box = h("div.poker-live"); poker.replaceChildren(box); pokerLive(box, me, () => render()); };
    poker.replaceChildren(gsec("poker", "🃏 Texas Hold'em", appBtn("poker"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("button.btn", { onclick: () => pokerStartDialog(open) }, "▶ ", T("Open a table"))]));
  };
  const song = h("div");
  const showSong = async () => {
    let g = null; try { g = await call("community/song"); } catch {}
    const open = () => { const b = h("div.song-live"); song.replaceChildren(b); songLive(b, me, () => render()); };
    song.replaceChildren(gsec("song", "🎵 " + I18N.tr(T("Guess the song")), appBtn("song"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("button.btn", { onclick: () => songStartDialog(open) }, "▶ ", T("Open the game"))]));
  };
  const showCards = async kind => {
    let g = null; try { g = await call("community/cards/" + kind); } catch {}
    const box = cardBoxes[kind];
    const open = () => { const b = h("div.cards-live"); box.replaceChildren(b); cardsLive(b, me, () => render(), kind); };
    box.replaceChildren(gsec(kind, CARD_GAMES[kind].icon + " " + CARD_GAMES[kind].title, appBtn(kind), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : h("div.row.wrap", h("button.btn", { onclick: () => cardsStartDialog(kind, false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
          h("button.btn.ghost", { onclick: () => cardsStartDialog(kind, true, open) }, "🤖 ", T("Alone against bots")))));
  };
  const showDomino = async () => {
    let g = null; try { g = await call("community/domino"); } catch {}
    const open = () => { const b = h("div.dm-live"); domino.replaceChildren(b); dominoLive(b, me, () => render()); };
    domino.replaceChildren(gsec("domino", "🁫 Domino", appBtn("domino"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : h("div.row.wrap", h("button.btn", { onclick: () => dominoStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
          h("button.btn.ghost", { onclick: () => dominoStartDialog(true, open) }, "🤖 ", T("Alone against bots")))));
  };
  // Pair Hunt: play, then its own content – the photo sets (shared with the pairs game of the game corner)
  const pjPlay = h("div"), pjSets = h("div"), pjRewards = h("div");
  const cPair = csec("paarjagd", appBtn("paarjagd"), "📷 " + I18N.tr(T("Photo sets")), pjRewards);
  cPair.play.append(pjPlay); cPair.list.append(pjSets);
  paarjagd.append(cPair.el);
  const showPaarjagd = async () => {
    let g = null; try { g = await call("community/paarjagd"); } catch {}
    const open = () => { const b = h("div.pj-live"); paarjagd.replaceChildren(b); paarjagdLive(b, me, () => render()); };
    pjPlay.replaceChildren(g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : h("div.row.wrap", h("button.btn", { onclick: () => paarjagdStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
          h("button.btn.ghost", { onclick: () => paarjagdStartDialog(true, open) }, "🤖 ", T("Alone against bots"))));
    pjRewards.replaceChildren(await gameRewardsRow("paarjagd"));
    const ps = await photoSets(cPair.count);
    cPair.actions.replaceChildren(h("button.btn", { onclick: ps.newDialog }, "+ ", T("New")));
    pjSets.replaceChildren(ps.el);
  };
  const showWerbinich = async () => {
    let g = null; try { g = await call("community/werbinich"); } catch {}
    const open = () => { const b = h("div.wb-live"); werbinich.replaceChildren(b); werbinichLive(b, me, () => render()); };
    werbinich.replaceChildren(gsec("werbinich", "🎭 " + I18N.tr(T("Who am I?")), appBtn("werbinich"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("button.btn", { onclick: () => werbinichStartDialog(open) }, "👨‍👩‍👧 ", T("Open a family table"))],
      await gameRewardsRow("werbinich")));
  };
  const showKartenlauf = async () => {
    let g = null; try { g = await call("community/kartenlauf"); } catch {}
    const open = () => { const b = h("div.kl-live"); kartenlauf.replaceChildren(b); kartenlaufLive(b, me, () => render()); };
    kartenlauf.replaceChildren(gsec("kartenlauf", "🏁 " + I18N.tr(T("Card Race")), appBtn("kartenlauf"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => kartenlaufStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => kartenlaufStartDialog(true, open) }, "🤖 ", T("Alone against bots")))],
      await gameRewardsRow("kartenlauf")));
  };
  const showStadtland = async () => {
    let g = null; try { g = await call("community/stadtland"); } catch {}
    const open = () => { const b = h("div.sl-live"); stadtland.replaceChildren(b); stadtlandLive(b, me, () => render()); };
    stadtland.replaceChildren(gsec("stadtland", "🏙️ " + I18N.tr(T("City, Country, River")), appBtn("stadtland"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("button.btn", { onclick: () => stadtlandStartDialog(open) }, "👨‍👩‍👧 ", T("Open a family table"))],
      await gameRewardsRow("stadtland")));
  };
  const showZeichnen = async () => {
    let g = null; try { g = await call("community/zeichnen"); } catch {}
    const open = () => { const b = h("div.zr-live"); zeichnen.replaceChildren(b); zeichnenLive(b, me, () => render()); };
    zeichnen.replaceChildren(gsec("zeichnen", "🎨 " + I18N.tr(T("Draw & Guess")), appBtn("zeichnen"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("button.btn", { onclick: () => zeichnenStartDialog(open) }, "👨‍👩‍👧 ", T("Open a family table"))],
      await gameRewardsRow("zeichnen")));
  };
  const showWuerfel = async () => {
    let g = null; try { g = await call("community/wuerfel"); } catch {}
    const open = () => { const b = h("div.fw-live"); wuerfel.replaceChildren(b); wuerfelLive(b, me, () => render()); };
    wuerfel.replaceChildren(gsec("wuerfel", "🎲 " + I18N.tr(T("Five Dice")), appBtn("wuerfel"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => wuerfelStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => wuerfelStartDialog(true, open) }, "🤖 ", T("Alone against bots")))],
      await gameRewardsRow("wuerfel")));
  };
  const showHeimwaerts = async () => {
    let g = null; try { g = await call("community/heimwaerts"); } catch {}
    const open = () => { const b = h("div.hw-live"); heimwaerts.replaceChildren(b); heimwaertsLive(b, me, () => render()); };
    heimwaerts.replaceChildren(gsec("heimwaerts", "🏠 " + I18N.tr(T("Homeward")), appBtn("heimwaerts"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => heimwaertsStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => heimwaertsStartDialog(true, open) }, "🤖 ", T("Alone against bots")))],
      await gameRewardsRow("heimwaerts")));
  };
  const showJump = async () => {
    let g = null; try { g = await call("community/jump"); } catch {}
    const open = () => { const b = h("div.ju-live"); jump.replaceChildren(b); jumpLive(b, me, () => render()); };
    jump.replaceChildren(gsec("jump", "🦘 Jump", appBtn("jump"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => jumpStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => jumpStartDialog(true, open) }, JU_ICON, " ", T("Alone")))],
      await gameRewardsRow("jump")));
  };
  const showSternlauf = async () => {
    let g = null; try { g = await call("community/sternlauf"); } catch {}
    const open = () => { const b = h("div.sr-live"); sternlauf.replaceChildren(b); sternlaufLive(b, me, () => render()); };
    sternlauf.replaceChildren(gsec("sternlauf", "🌠 " + I18N.tr(T("Star Runner")), appBtn("sternlauf"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => sternlaufStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => sternlaufStartDialog(true, open) }, SR_ICON, " ", T("Alone")))],
      await gameRewardsRow("sternlauf")));
  };
  const showSnack = async () => {
    let g = null; try { g = await call("community/snack"); } catch {}
    const open = () => { const b = h("div.sn-live"); snack.replaceChildren(b); snackLive(b, me, () => render()); };
    snack.replaceChildren(gsec("snack", "🍔 " + I18N.tr(T("Snack Rush")), appBtn("snack"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => snackStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => snackStartDialog(true, open) }, SN_ICON, " ", T("Alone")))],
      await gameRewardsRow("snack")));
  };
  const showVerkehr = async () => {
    let g = null; try { g = await call("community/verkehr"); } catch {}
    const open = () => { const b = h("div.vk-live"); verkehr.replaceChildren(b); vkLive(b, me, () => render()); };
    verkehr.replaceChildren(gsec("verkehr", "🚦 " + I18N.tr(T("Traffic Cadet")), appBtn("verkehr"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => vkStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => vkStartDialog(true, open) }, VK_ICON, " ", T("Alone")))],
      await gameRewardsRow("verkehr")));
  };
  const showLangstrecke = async () => {
    let g = null; try { g = await call("community/langstrecke"); } catch {}
    let r = {}; try { r = await call("community/langstrecke/rules"); } catch {}
    const open = () => { const b = h("div.le-live"); langstrecke.replaceChildren(b); langstreckeLive(b, me, () => render()); };
    const f = { minutes: leMinutes(r.minutes), weather: leWeather(r.weather ?? 1), difficulty: leDiff(r.difficulty), team_size: leSize(r.team_size) };
    const defaults = h("div.pj-rewards", h("b", "⚙️ ", T("Race defaults")),
      h("div.grid2", h("label.field", T("Race length"), f.minutes), h("label.field", T("Weather"), f.weather),
        h("label.field", T("Difficulty"), f.difficulty), h("label.field", T("People per team"), f.team_size)),
      h("div.row", h("button.btn.small", { onclick: async () => {
        try { await call("community/langstrecke/rules", { method: "PUT", body: { minutes: +f.minutes.value, weather: +f.weather.value, difficulty: f.difficulty.value, team_size: +f.team_size.value } }); toast(T("Saved"), "good"); } catch (e) { toast(e.message, "bad"); }
      } }, T("Save"))));
    langstrecke.replaceChildren(gsec("langstrecke", "🏎️ " + I18N.tr(T("24h Endurance")), appBtn("langstrecke"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => langstreckeStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => langstreckeStartDialog(true, open) }, LE_ICON, " ", T("Alone")))],
      defaults, await gameRewardsRow("langstrecke")));
  };
  const showKlatsch = async () => {
    let g = null; try { g = await call("community/klatsch"); } catch {}
    const open = () => { const b = h("div.kb-live"); klatsch.replaceChildren(b); klatschLive(b, me, () => render()); };
    klatsch.replaceChildren(gsec("klatsch", "👏 " + I18N.tr(T("Clap the Beat")), appBtn("klatsch"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => klatschStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => klatschStartDialog(true, open) }, KB_ICON, " ", T("Alone")))],
      await gameRewardsRow("klatsch")));
  };
  const showVerboten = async () => {
    let g = null; try { g = await call("community/verboten"); } catch {}
    const open = () => { const b = h("div.vw-live"); verboten.replaceChildren(b); verbotenLive(b, me, () => render()); };
    verboten.replaceChildren(gsec("verboten", "🚫 " + I18N.tr(T("Forbidden Words")), appBtn("verboten"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("button.btn", { onclick: () => verbotenStartDialog(open) }, "👨‍👩‍👧 ", T("Open a family table"))],
      await gameRewardsRow("verboten")));
  };
  const showJass = async () => {
    let g = null; try { g = await call("community/jass"); } catch {}
    const open = () => { const b = h("div.ja-live"); jass.replaceChildren(b); jassLive(b, me, () => render()); };
    jass.replaceChildren(gsec("jass", "♣️ " + I18N.tr(T("Jass")), appBtn("jass"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => jassStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => jassStartDialog(true, open) }, "🤖 ", T("With 3 bots")))],
      await gameRewardsRow("jass")));
  };
  const showWerwolf = async () => {
    let g = null; try { g = await call("community/werwolf"); } catch {}
    const open = () => { const b = h("div.ww-live"); werwolf.replaceChildren(b); werwolfLive(b, me, () => render()); };
    werwolf.replaceChildren(gsec("werwolf", "🐺 " + I18N.tr(T("Werewolves")), appBtn("werwolf"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("button.btn", { onclick: () => werwolfStartDialog(open) }, "👨‍👩‍👧 ", T("Open a family table"))],
      await gameRewardsRow("werwolf")));
  };
  const showSchach = async () => {
    const open = id => { const b = h("div.ch-live"); schach.replaceChildren(b); schachLive(b, me, () => render(), id); };
    schach.replaceChildren(gsec("schach", "♟️ " + I18N.tr(T("Chess")), appBtn("schach"),
      await schachPanel(me, open), await gameRewardsRow("schach")));
  };
  const showDorfmarkt = async () => {
    let g = null; try { g = await call("community/dorfmarkt"); } catch {}
    const open = () => { const b = h("div.mk-live"); dorfmarkt.replaceChildren(b); dorfmarktLive(b, me, () => render()); };
    dorfmarkt.replaceChildren(gsec("dorfmarkt", "🏘️ " + I18N.tr(T("Village Market")), appBtn("dorfmarkt"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => dorfmarktStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => dorfmarktStartDialog(true, open) }, "🤖 ", T("Alone against bots")))],
      await gameRewardsRow("dorfmarkt")));
  };
  const showEscape = async () => {
    let g = null; try { g = await call("community/escape"); } catch {}
    const open = () => { const b = h("div.er-live"); escape.replaceChildren(b); escapeLive(b, me, () => render()); };
    let info = null; try { info = (await call("community/escape/rules")).played; } catch {}
    escape.replaceChildren(gsec("escape", "🗝️ " + I18N.tr(T("Escape Room")), appBtn("escape"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [info ? h("p.small", "🧩 ", I18N.tr(T("{0} of {1} riddles not played yet – round {2}")).replace("{0}", info.new).replace("{1}", info.total).replace("{2}", info.round)) : null,
         h("button.btn", { onclick: () => escapeStartDialog(open) }, "👨‍👩‍👧 ", T("Open a family table"))],
      await gameRewardsRow("escape")));
  };
  const showStempeljagd = async () => {
    let g = null; try { g = await call("community/stempeljagd"); } catch {}
    const open = () => { const b = h("div.sj-live"); stempeljagd.replaceChildren(b); stempeljagdLive(b, me, () => render()); };
    stempeljagd.replaceChildren(gsec("stempeljagd", "🏛️ " + I18N.tr(T("Beat the Bureaucracy")), appBtn("stempeljagd"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => stempeljagdStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => stempeljagdStartDialog(true, open) }, "🤖 ", T("Alone against bots")))],
      await gameRewardsRow("stempeljagd")));
  };
  // the small games of the game corner: only the status (they run on the device)
  const arcade = ["ttt", "pingpong", "sudoku", "patience", "slots"].map(k => {
    const [, ic, name] = GAME_LIST.find(g => g[0] === k);
    return h("div", gsec(k, ic + " " + I18N.tr(name), appBtn("arcade/" + k)));
  });
  // the special quiz «Family Quest Facts» (questions from the family's data) – on by default
  const factsOn = h("input", { type: "checkbox", checked: s.quiz_facts !== false, onchange: async () => {
    await call("parent/settings", { method: "PUT", body: { quiz_facts: factsOn.checked } }); toast(T("Saved"), "good"); } });
  const factsSet = h("div.pj-rewards", h("label.check", factsOn, h("span", "📊 ", T("Special quiz «Family Quest Facts»: questions from our own data (chores, games, records, shop, pets) – nothing from the parent area"))));
  const cQuiz = csec("quiz", appBtn("quiz"), "🎯 " + I18N.tr(T("Quizzes")), factsSet);
  cQuiz.list.append(live, quizzes);
  const quiz = h("div", cQuiz.el);
  // adventure games: the ones of the family (stories.js storyShelf, type «game») – approve, edit, import, new
  const cAdv = csec("adventuregame", null, "🗝️ " + I18N.tr(T("Adventure games")));
  cAdv.play.append(h("button.btn", { onclick: () => openInApp("advgames") }, "🧭 ", T("Play alone")));
  const adventuregame = h("div", cAdv.el);
  const blocks = { quiz, adventuregame, bingo, song, tschau: cardBoxes.tschau, karussell: cardBoxes.karussell, domino, paarjagd, werbinich, kartenlauf, stadtland, zeichnen, wuerfel,
    langstrecke,
    heimwaerts, jump, sternlauf, snack, verkehr, klatsch, verboten, jass, werwolf, schach, dorfmarkt, escape, stempeljagd, poker, ...Object.fromEntries(["ttt", "pingpong", "sudoku", "patience", "slots"].map((k, i) => [k, arcade[i]])) };
  // only the games of this app's channel: the server leaves out games still in development (channel.py DEV_GAMES)
  for (const k of Object.keys(blocks)) if (!(k in data.access)) delete blocks[k];
  // the groups stand on the page background like «Family» and «Settings»: the heading with its ⓘ, the folded games below
  const custom = h("section.cg-group", setGroup("Custom games", "🛠️", T("Custom games")),
    ...CUSTOM_GAMES.filter(k => blocks[k]).map(k => blocks[k]));
  // the other games in the groups of the children's app; a game in no group goes to the game night
  const grouped = new Set(GAME_GROUPS.flatMap(g => g[3]));
  const groups = GAME_GROUPS.map(([id, ic, name, keys], i) => h("section.cg-group.game-group", { "data-group": id }, setGroup(name, ic, name),
    ...[...keys, ...(i ? [] : Object.keys(blocks).filter(k => !grouped.has(k) && !CUSTOM_GAMES.includes(k)))].filter(k => blocks[k]).map(k => blocks[k])));
  for (const [k, el] of Object.entries(blocks)) {
    const g = GAME_LIST.find(x => x[0] === k);
    el.classList.add("game-block");
    el.dataset.find = [k, g ? I18N.tr(g[2]) : "", g ? g[2] : ""].join(" ").toLowerCase();
  }
  // search: filters the games by name – remembered while the page is open
  const search = h("input.pack-search", { type: "search", placeholder: "🔍 " + I18N.tr(T("Search games …")), value: P.gameSearch || "",
    "aria-label": T("Search games …"), oninput: () => { P.gameSearch = search.value; filter(); } });
  const none = noMatch(T("No game found."), () => { search.value = ""; P.gameSearch = ""; filter(); });
  const filter = () => {
    const q = (search.value || "").trim().toLowerCase();
    let shown = 0;
    for (const el of Object.values(blocks)) {
      el.hidden = !!q && !el.dataset.find.includes(q); if (!el.hidden) shown++;
      if (q && !el.hidden) el.querySelectorAll("details.game-sec").forEach(d => { d.open = true; });   // a game searched for opens
    }
    none.hidden = !q || shown > 0;
    custom.hidden = CUSTOM_GAMES.every(k => !blocks[k] || blocks[k].hidden);
    for (const g of groups) g.hidden = !g.querySelector(":scope > .game-block:not([hidden])");
  };
  // for every game: who begins, guests, all on / off
  const starter = h("select", { onchange: async () => { await call("parent/settings", { method: "PUT", body: { game_starter: starter.value } }); toast(T("Saved"), "good"); } },
    ...[["dice", "🎲 " + I18N.tr(T("The dice decides"))], ["leader", "👑 " + I18N.tr(T("Whoever leads the game"))], ["choose", "👉 " + I18N.tr(T("Whoever leads chooses a player"))]]
      .map(([k, n]) => h("option", { value: k, selected: (s.game_starter || "dice") === k }, n)));
  const guests = h("input", { type: "checkbox", checked: s.games_guests !== false, onchange: async () => {
    await call("parent/settings", { method: "PUT", body: { games_guests: guests.checked } }); toast(T("Saved"), "good"); } });
  const general = setFold("games.general", ["🎛️ ", T("General")], h("div.games-general",
    h("div.row", h("button.btn.small.ghost", { onclick: async () => { await access.allTo("all"); render(); } }, "✓ ", T("All on")),
      h("button.btn.small.ghost", { onclick: async () => { await access.allTo("off"); render(); } }, "✕ ", T("All off"))),
    h("label.field", T("Who begins a game (card and board games)"), starter),
    h("label.check", guests, h("span", T("Guests may join (whoever leads a game shows a QR code; guests type a name and play – nothing else of the app is open to them)")))));
  general.querySelector(".set-head > h2").dataset.ik = "games.general";
  general.querySelector(".set-status").textContent = starter.selectedOptions[0] ? starter.selectedOptions[0].textContent : "";
  starter.addEventListener("change", () => { general.querySelector(".set-status").textContent = starter.selectedOptions[0].textContent; });
  main.append(h("h1", T("Games")), partyCard(),
    search, h("section.cg-group.games-all", setGroup("games.all", "⚙️", T("For all games")), general, batterySettingsCard()), runningGamesBox(), custom, none, ...groups);
  filter();
  showLive(); showBingo(); showSong(); showPoker(); showCards("tschau"); showCards("karussell"); showDomino(); showPaarjagd(); showWerbinich(); showKartenlauf(); showStadtland(); showZeichnen(); showWuerfel(); showHeimwaerts(); showJump(); showSternlauf(); showSnack(); showVerkehr(); showKlatsch(); showVerboten(); showJass(); showWerwolf(); showSchach(); showDorfmarkt(); showEscape();
  if (blocks.langstrecke) showLangstrecke();
  if (blocks.stempeljagd) showStempeljagd();
  quizzesPanel(quizzes, me, showLive, { actions: cQuiz.actions, withImport: true, onCount: cQuiz.count, play: cQuiz.play });
  if (blocks.adventuregame) storyShelf(cAdv.list, { types: ["game"], actions: cAdv.actions, onCount: cAdv.count });
}

// live games (Paarjagd, «Wer bin ich?», Kartenlauf, Stadt-Land-Fluss, «Zeichnen & Raten», «Fünf Würfel», «Verbotene Wörter»): coins for places 1 / 2 / 3 (only family tables with at least two people of the family)
// Jass: only place 1 – the coins for each person of the family in the winning team
async function gameRewardsRow(game) {
  let r = {};
  try { r = await call("parent/game-rewards"); } catch {}
  const cur = r[game] || [10, 5, 2];
  const inputs = cur.map(v => h("input.pj-reward", { type: "number", min: 0, max: 1000, step: 1, value: v, inputmode: "numeric" }));
  if (game === "jass" || game === "escape") {
    const save1 = async () => {
      const v = Number(inputs[0].value);
      if (!Number.isInteger(v) || v < 0 || v > 1000) return toast(T("Three numbers of coins (0 to 1000) are needed"), "bad");
      try { await call("parent/game-rewards", { method: "PUT", body: { [game]: [v, cur[1], cur[2]] } }); toast(T("Saved"), "good"); } catch {}
    };
    return h("div.pj-rewards", h("b", "🪙 ", T("Coins for each person of the family in the winning team"),
        fieldInfo(game === "escape" ? T("Only when the team escaped (together: everybody; two teams: the team out first) – at a family table with at least two people of the family, not for guests.")
          : T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."))),
      h("div.row", inputs[0], h("button.btn.small", { onclick: save1 }, T("Save"))));
  }
  const save = async () => {
    const vals = inputs.map(i => Number(i.value));
    if (vals.some(v => !Number.isInteger(v) || v < 0 || v > 1000)) return toast(T("Three numbers of coins (0 to 1000) are needed"), "bad");
    try { await call("parent/game-rewards", { method: "PUT", body: { [game]: vals } }); toast(T("Saved"), "good"); } catch {}
  };
  // when coins are paid: in the ⓘ of the row (the photo sets of the Paarjagd: in its section of «Custom games», photoSets)
  const rule = game === "schach" ? T("Only the winner gets coins, only after at least 10 own moves – not against the easy bot, not on one device, not against guests.")
    : game === "werwolf" ? T("Werwölfe: everybody of the family on the winning side gets the coins of place 1 – only at a table with at least two people of the family, only for a game played to the end, not for guests.")
    : game !== "paarjagd" ? T("Coins only at a table with at least two people of the family – not for guests.")
    : T("Coins only at a family table with at least two people of the family – not alone against bots, not for guests or bots.");
  return h("div.pj-rewards", h("b", "🪙 ", game === "schach" ? T("Coins for a win: against the family / the hard bot / the normal bot") : T("Coins for place 1 / 2 / 3"), fieldInfo(rule)),
    h("div.row", ...inputs.flatMap((i, k) => [k ? h("span.muted", "/") : null, i]).filter(Boolean), h("button.btn.small", { onclick: save }, T("Save"))));
}
