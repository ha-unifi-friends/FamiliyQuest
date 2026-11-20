// «Escape Room» – the live riddle game for the family (familyquest/escape.py, escape_riddles.py): every room is a
// scene with objects; tap an object to open its riddle. Solved riddles reveal parts of the door code; the door needs
// all of them. Together (one team) or two teams with the same rooms; guests via QR code, no bots.
// escapeLive(box, me, back) runs the table, escapeStartDialog(onStarted) sets the rules. The server makes and checks
// every riddle – the app never gets a solution; mechanical puzzles are played here and the moves are checked there.
"use strict";

const ER_ICON = "🗝️";
const erName = () => I18N.tr(T("Escape Room"));
const ER_POLL_MS = 1000;
const ER_LEVELS = { easy: ["🐣", T("Easy")], medium: ["🦊", T("Medium")], hard: ["🐉", T("Hard")], mixed: ["📈", T("Mixed (getting harder)")] };
const ER_TEAMS = ["🟣", "🟠"];
const ER_SPOTS = [[17, 26], [83, 26], [15, 70], [85, 70], [50, 86]];
// a few things in every room that are only there to look at: emoji, left %, top %, size (rem)
const ER_PROPS = {
  wizard: [["✨", 30, 10, 1.4], ["🌟", 72, 14, 1.1], ["📜", 62, 60, 1.3], ["🍄", 35, 92, 1.1]],
  pirate: [["🪝", 30, 8, 1.4], ["🐚", 64, 92, 1.1], ["🏴‍☠️", 70, 12, 1.4], ["🪙", 36, 58, 1]],
  space: [["⭐", 28, 9, 1], ["✨", 70, 14, 1.2], ["🌍", 74, 7, 1.5], ["🔧", 36, 92, 1.1]],
  treehouse: [["🍃", 26, 8, 1.4], ["🍂", 72, 12, 1.2], ["🌰", 64, 92, 1.1], ["🧸", 34, 58, 1.2]],
  clock: [["⏲️", 28, 9, 1.4], ["🔩", 64, 92, 1.1], ["⌚", 70, 13, 1.2], ["🕯️", 35, 60, 1.1]],
  ice: [["❄️", 30, 9, 1.3], ["🌨️", 72, 12, 1.4], ["🧊", 64, 93, 1.1], ["✨", 36, 58, 1]],
  jungle: [["🌿", 26, 8, 1.5], ["🦋", 72, 14, 1.2], ["🍌", 64, 92, 1.1], ["🌴", 35, 58, 1.3]],
  dragon: [["🕸️", 27, 9, 1.5], ["🪨", 64, 93, 1.2], ["💰", 36, 58, 1.1], ["🦴", 72, 14, 1.1]],
};
const ER_FRAG_COL = { red: "#e03131", yellow: "#fcc419", blue: "#1c7ed6", green: "#2f9e44" };
const erTeam = k => ER_TEAMS[+k] + " " + I18N.tr(T("Team {0}")).replace("{0}", k === "1" ? "B" : "A");
const erCoins = n => n + " 🪙";
const erClock = s => { s = Math.max(0, Math.round(s)); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };
const erLang = () => (I18N.base || "en").split("-")[0];

// a text of the server: [key, arg, …] – the key and the args are translated ({"t": key}), {"L": {lang: …}} is the
// device's language, {"line": […]} a text inside the text
function erText(x) {
  if (x == null) return "";
  if (Array.isArray(x)) {
    let s = I18N.tr(x[0]);
    x.slice(1).forEach((a, i) => { s = s.split("{" + i + "}").join(erArg(a)); });
    return s;
  }
  return erArg(x);
}
function erArg(a) {
  if (a == null) return "";
  if (typeof a !== "object") return String(a);
  if (a.L) return String(a.L[erLang()] ?? a.L.en ?? "");
  if (a.line) return erText(a.line);
  if (a.t) return I18N.tr(a.t);
  return "";
}
const erVal = v => (v && typeof v === "object" && v.L) ? (v.L[erLang()] ?? v.L.en) : v;

function escapeRulesView(st) {
  const items = [T("Every room hides riddles in its objects – tap an object to open its riddle. Everybody of the team sees the same room and may try."),
    T("Every solved riddle reveals a part of the door code. The door needs all parts together – then on to the next room."),
    I18N.tr(T("A hint costs {0} seconds, a wrong answer {1} seconds – the hints are shown to the whole team.")).replace("{0}", st ? st.hint_s : 60).replace("{1}", st ? st.wrong_s : 10),
    T("Two teams play the same rooms with the same riddles – the first team out (counting the hint seconds) wins. You only see the other team's progress."),
    T("The riddles are new every game; riddles you already played come again only when all were played."),
    st && st.coins_on ? I18N.tr(T("Coins for each person of the family in the team that escaped and won: {0}")).replace("{0}", erCoins((st.rewards || [0])[0])) : null,
    T("Coins only at a table with at least two people of the family – not for guests.")].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

async function escapeStartDialog(onStarted) {
  let r = {};
  try { r = await api("community/escape/rules"); } catch {}
  const played = r.played || { types: {} };
  let rooms = r.rooms || 3, level = r.level || "mixed", mode = r.mode || "together", time = r.time || 0;
  const types = new Set(r.types || Object.keys(r.type_names || {}));
  const seg = (list, cur, label, set) => {
    const box = h("div.seg");
    const draw = () => box.replaceChildren(...list.map(n => h("button" + (n === cur ? ".on" : ""), { type: "button", onclick: () => { cur = n; set(n); draw(); } }, label(n))));
    draw();
    return box;
  };
  const lvBox = h("div.er-levels");
  const drawLv = () => lvBox.replaceChildren(...Object.entries(ER_LEVELS).map(([k, [ic, n]]) => h("button.wb-cat" + (k === level ? ".on" : ""),
    { type: "button", "aria-pressed": String(k === level), onclick: () => { level = k; drawLv(); drawCount(); } }, h("span.wb-cat-ic", ic), h("span", n))));
  const tyBox = h("div.er-types");
  const count = h("p.small.er-count");
  const drawCount = () => {
    const fit = (r.riddles || []).filter(x => types.has(x.type) && (level === "mixed" || x.levels.includes(level)));
    count.replaceChildren("🧩 ", I18N.tr(T("{0} of {1} riddles not played yet – round {2}")).replace("{0}", played.new ?? "?").replace("{1}", played.total ?? "?").replace("{2}", played.round ?? 1),
      h("br"), h("span.muted", I18N.tr(T("{0} riddles fit your choice")).replace("{0}", fit.length)));
  };
  const drawTypes = () => tyBox.replaceChildren(...Object.keys(r.type_names || {}).map(k => {
    const on = types.has(k), p = played.types[k] || {};
    return h("button.er-type" + (on ? ".on" : ""), { type: "button", "aria-pressed": String(on), onclick: () => {
      if (on && types.size === 1) return; on ? types.delete(k) : types.add(k); drawTypes(); drawCount(); } },
      h("span.er-type-ic", (r.type_icons || {})[k] || "🧩"), h("span.er-type-n", I18N.tr(r.type_names[k])),
      h("small.muted", (p.new ?? 0) + "/" + (p.total ?? 0) + " ✨"));
  }));
  drawLv(); drawTypes(); drawCount();
  const coins = (r.rewards || [0])[0] > 0 ? h("p.small.pj-coins", "🪙 ", I18N.tr(T("Coins for each person of the family in the team that escaped and won: {0}")).replace("{0}", erCoins(r.rewards[0])), h("br"),
    h("span.muted", T("Coins only at a table with at least two people of the family – not for guests."))) : null;
  const m = modal(h("div.form.er-start", h("h2", ER_ICON, " ", erName()),
    h("p.small.muted", T("Solve the riddles of every room together to find the door code – and get out! Live on every device, guests via QR code.")),
    h("div.field", h("b", T("Rooms")), seg(r.rooms_choice || [1, 2, 3, 4, 5], rooms, n => String(n), n => { rooms = n; })),
    h("div.field", h("b", T("Difficulty")), lvBox),
    h("div.field", h("b", T("Kinds of riddles")), tyBox, count),
    h("div.field", h("b", T("Play")), seg(r.modes || ["together", "teams"], mode, n => n === "teams" ? "⚔️ " + I18N.tr(T("Two teams")) : "🤝 " + I18N.tr(T("All together")), n => { mode = n; })),
    h("div.field", h("b", T("Time limit")), seg(r.times || [0, 15, 30, 45], time, n => n ? n + " min" : I18N.tr(T("none")), n => { time = n; })),
    coins,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      try { await api("community/escape/start", { method: "POST", body: { rooms, level, types: [...types], mode, time } }); m.close(); onStarted(); }
      catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
}

function escapeLive(box, me, back) {
  let st = null, timer = null, tick = null, alive = true, lastSig = "", busy = false, cheered = false;
  let openKey = null, fetchedAt = Date.now(), lastRoom = null, lastSolved = 0;
  const draft = {}, local = {};
  const myId = String(me.id);
  box.classList.add("er-live");
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => {
    alive = false; clearTimeout(timer); clearInterval(tick);
    box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open");
  };
  window.addEventListener("hashchange", stop, { once: true });
  const take = x => { if (x && Array.isArray(x.players)) { st = x; fetchedAt = Date.now(); } };
  const act = async (path, body) => {
    if (busy) return null;
    busy = true;
    try { const x = await api("community/escape/" + path, { method: "POST", body }); take(x.state || x); draw(true); return x; }
    catch (e) { toast(e.message, "bad"); try { take(await api("community/escape")); draw(true); } catch {} return null; }
    finally { busy = false; }
  };
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try { take(await api("community/escape")); draw(); } catch {}
    timer = setTimeout(poll, ER_POLL_MS);
  }
  const player = id => (st.players || []).find(p => p.id === id) || {};
  const who = id => player(id).name || "?";
  const room = () => st && st.room;
  const riddle = key => room() && room().riddles.find(r => r.key === key);

  async function submit(key, answer) {
    const x = await act("answer", key == null ? { answer } : { key, answer });
    if (!x) return;
    if (x.ok) { try { Sound.play("right"); } catch {} if (key != null) { delete draft[key]; delete local[key]; } }
    else { try { Sound.play("wrong"); } catch {} toast(I18N.tr(T("Not quite – try again! (+{0} s)")).replace("{0}", st.wrong_s), "bad"); }
  }

  // «Invite guests» (☰ and the button in the lobby box): the game key – null for solo tables, guests, finished games
  function invite() { return !me.guest && st.status !== "done" && st.phase === "lobby" ? "escape" : null; }
  function draw(force) {
    if (!alive || !box.isConnected) return;
    if (st && !Array.isArray(st.players)) st = null;
    const sig = JSON.stringify(st, (k, v) => (k === "now" || k === "elapsed") ? undefined : v) + "|" + openKey;
    if (sig === lastSig && !force) return;
    const typing = document.activeElement && document.activeElement.classList.contains("er-text") && box.contains(document.activeElement);
    if (typing && !force && st && st.phase === "play") return;          // do not take the keyboard away while somebody types
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    clearInterval(tick);
    if (!st) return show(h("section.card.center", h("div.big-ic", ER_ICON), h("h2", T("No game right now")), h("button.btn", { onclick: back }, T("Back"))));
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    if (st.phase === "done") { openKey = null; return show(head(), result()); }
    if (st.phase === "lobby") {
      if (!st.joined) return show(close, head(), h("section.card.center", h("p", T("Play along on this device?")),
        h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join"))), seats(), hostBar());
      return show(close, head(), h("section.card.center", h("h2", T("Waiting for the start …")),
        h("p.muted", T("Everybody joins on their own device.")), seats(), inviteBtn(invite()), ruleChips(),
        st.coins_on ? h("p.small", "🪙 ", I18N.tr(T("Coins for each person of the family in the team that escaped and won: {0}")).replace("{0}", erCoins(st.rewards[0]))) : null), hostBar());
    }
    const rm = room();
    if (rm) {
      if (lastRoom !== null && rm.index !== lastRoom) { openKey = null; try { Sound.play("done"); } catch {} toast("🚪 " + I18N.tr(T("The door is open – on to the next room!")), "good"); }
      lastRoom = rm.index;
      const solved = rm.riddles.filter(r => r.solved).length;
      if (solved > lastSolved && openKey == null) { try { Sound.play("right"); } catch {} }
      lastSolved = solved;
    }
    if (!rm) return show(close, head(), progressBars(), h("section.card.center", h("p.muted", T("You are watching – the game is running."))));
    if (rm.out) return show(close, head(), progressBars(), h("section.card.center.er-out", h("div.big-ic", "🎉"), h("h2", T("Your team is out!")),
      h("p.muted", T("Wait for the other team …"))));
    show(close, head(), progressBars(), scene(rm), footer(rm), openKey ? sheet(rm) : null);
    tick = setInterval(clock, 500); clock();
  }

  function head() {
    const lead = isHost() && st.status !== "done";
    const menu = gameMenu({ rules: () => escapeRulesView(st),
      invite: invite(),
      actions: [
        { ic: "🔀", label: T("Mix teams"), hidden: !lead || st.phase !== "lobby" || !st.teams, onclick: () => act("mix") },
        { ic: "⏹", label: T("End the game"), danger: true, hidden: !lead, confirm: T("End the game? Nobody escapes then."), onclick: () => act("end") }],
      onLeave: st.status !== "done" ? () => { stop(); back(); } : null });
    const rm = room();
    return h("div.quiz-head.dm-head.er-head", h("div.row.head-title", menu, h("h1", rm && st.phase === "play" ? [rm.emoji, " ", C(I18N.tr(rm.name))] : [ER_ICON, " ", erName()])),
      st.phase === "play" ? h("div.row", h("span.chip.er-clock", "⏱ ", h("b.er-time"))) : null);
  }

  function clock() {
    if (!alive || !st || st.phase !== "play") return;
    const now = st.elapsed + (Date.now() - fetchedAt) / 1000;
    const left = st.limit ? st.limit - now : null;
    box.querySelectorAll(".er-time").forEach(x => { x.textContent = left != null ? erClock(left) : erClock(now); });
    box.querySelectorAll(".er-clock").forEach(x => x.classList.toggle("hurry", left != null && left < 60));
  }

  function ruleChips() {
    const lv = ER_LEVELS[st.rules.level] || ER_LEVELS.mixed;
    return h("div.sl-chips", h("span.chip", "🚪 ", I18N.tr(T("{0} rooms")).replace("{0}", st.rules.rooms)), h("span.chip", lv[0], " ", lv[1]),
      h("span.chip", "🧩 ", I18N.tr(T("{0} kinds of riddles")).replace("{0}", st.rules.types.length)),
      h("span.chip", st.rules.time ? "⏱ " + st.rules.time + " min" : "⏱ ∞"),
      st.teams ? h("span.chip", "⚔️ ", T("Two teams")) : h("span.chip", "🤝 ", T("All together")));
  }

  function hostBar() {
    if (!(isHost() && st.status !== "done" && st.phase === "lobby")) return null;
    return h("div.row.center.host-bar", h("button.btn", { disabled: st.rules.mode === "teams" && st.players.length < 2, onclick: () => act("begin") }, "▶ ", T("Start")));
  }

  function seat(p) {
    return h("div.dm-seat" + (p.id === myId ? ".dm-me" : ""), avatarSvg(p.avatar || {}, 30), C(p.name, "strong.small.dm-name"));
  }

  function seats() {
    if (!st.teams) return h("div.dm-seats", ...st.players.map(seat));
    return h("div.vw-teams", ...["0", "1"].map(k => h("div.vw-team.vw-t" + k, h("b", erTeam(k)), h("div.dm-seats", ...st.players.filter(p => p.team === k).map(seat)))));
  }

  // the own team's bar – with two teams the other team's bar below (only its progress)
  function progressBars() {
    const pr = st.progress || {};
    const bar = (k, mine) => {
      const p = pr[k] || { done: 0, total: 1 };
      return h("div.er-prog" + (mine ? ".mine" : ""), h("span.er-prog-n", st.teams ? erTeam(k) : "🚪 " + Math.min(st.n_rooms, (p.room || 0) + 1) + "/" + st.n_rooms),
        h("div.er-bar", h("i", { style: { width: Math.round(p.done / Math.max(1, p.total) * 100) + "%" } })),
        h("small", p.out ? "🎉" : p.done + "/" + p.total), mine && p.pen ? h("small.er-pen", { title: I18N.tr(T("Hints and wrong answers")) }, "+" + erClock(p.pen)) : null);
    };
    const mine = st.my_team || "0";
    return h("div.er-progs", bar(mine, true), st.teams ? bar(mine === "0" ? "1" : "0", false) : null);
  }

  // ---------- the room: a scene with the objects, the door and the decoration
  function scene(rm) {
    const items = rm.riddles.map(r => {
      const [x, y] = ER_SPOTS[r.spot] || [50, 50];
      return h("button.er-obj" + (r.solved ? ".done" : ""), { style: { left: x + "%", top: y + "%" }, onclick: () => { openKey = r.key; draw(true); },
        "aria-label": I18N.tr(r.obj_name) },
        h("span.er-obj-ic", r.obj), h("span.er-obj-n", I18N.tr(r.obj_name)),
        r.solved ? h("span.er-badge", "✓") : r.hints.length ? h("span.er-badge.hint", "💡" + r.hints.length) : null);
    });
    const [dx, dy] = ER_SPOTS[rm.decor.spot] || [50, 86];
    const decor = h("button.er-obj.er-decor", { style: { left: dx + "%", top: dy + "%" }, onclick: () => toast(rm.decor.emoji + " " + I18N.tr(rm.decor.text)) },
      h("span.er-obj-ic", rm.decor.emoji));
    const all = rm.riddles.every(r => r.solved);
    const door = h("button.er-door" + (all ? ".ready" : ""), { onclick: () => { openKey = "door"; draw(true); }, "aria-label": T("Exit door") },
      h("span.er-door-ic", "🚪"), h("span.er-obj-n", T("Exit door")));
    const props = (ER_PROPS[rm.theme] || []).map(([e, x, y, z]) => h("span.er-prop", { style: { left: x + "%", top: y + "%", fontSize: z + "rem" } }, e));
    return h("div.er-scene.er-th-" + rm.theme, h("div.er-floor"), h("div.er-window"), ...props, door, ...items, decor);
  }

  function fragView(f, kind) {
    if (!f) return h("span.er-frag.empty", "?");
    if (kind === "order") return h("span.er-frag", f.sym, " ", h("b", String(f.d)));
    if (kind === "sum") return h("span.er-frag", "🔢 ", h("b", String(f.n)));
    const c = Object.keys(ER_FRAG_COL)[f.c];
    return h("span.er-frag", h("i.er-gem", { style: { background: ER_FRAG_COL[c] } }), " ", h("b", "#" + f.pos));
  }

  function footer(rm) {
    const last = (rm.log || []).slice(-1)[0];
    const what = e => e.what === "solved" ? I18N.tr(T("{0} solved a riddle")).replace("{0}", who(e.who)) + (e.obj ? " " + e.obj : "")
      : e.what === "hint" ? I18N.tr(T("{0} took a hint")).replace("{0}", who(e.who)) + (e.obj ? " " + e.obj : "")
        : e.what === "door" ? I18N.tr(T("{0} opened the door!")).replace("{0}", who(e.who)) : I18N.tr(T("{0} found the way out!")).replace("{0}", who(e.who));
    return h("div.er-foot", h("div.er-frags", h("small.muted", "🔑 "), ...rm.riddles.map(r => fragView(r.frag, rm.door.kind))),
      h("p.small.er-log", { translate: "no" }, last ? "📣 " + what(last) : I18N.tr(T("Tap the objects in the room!"))));
  }

  // ---------- a riddle (or the door) on a sheet over the room
  function sheet(rm) {
    const closeIt = () => { openKey = null; draw(true); };
    if (openKey === "door") return doorSheet(rm, closeIt);
    const r = riddle(openKey);
    if (!r) { openKey = null; return null; }
    const lv = ER_LEVELS[r.level] || ["", ""];
    const body = [h("div.er-lines", ...r.lines.map(l => h("p", { translate: "no" }, erText(l)))),
      ...((r.peek && !r.solved) ? [peekBox(r)] : []), ...r.show.map(b => block(b))];
    let foot;
    if (r.solved) foot = h("div.er-solved", h("p", "✅ ", I18N.tr(T("Solved by {0}")).replace("{0}", who(r.solved.by))),
      h("p", T("Part of the door code:"), " ", fragView(r.frag, rm.door.kind)));
    else foot = input(r);
    const hints = h("div.er-hints", ...r.hints.map((x, i) => h("p.er-hint", { translate: "no" }, "💡 " + (i + 1) + ". " + erText(x))),
      !r.solved && r.hints.length < r.n_hints ? h("button.btn.small.ghost.er-hint-btn", { onclick: async () => {
        if ((await confirmDialog(I18N.tr(T("Take a hint? It costs {0} seconds for the team.")).replace("{0}", st.hint_s)))) act("hint", { key: r.key });
      } }, "💡 ", I18N.tr(T("Hint ({0} of {1})")).replace("{0}", r.hints.length + 1).replace("{1}", r.n_hints), h("small", " +" + st.hint_s + " s")) : null);
    return h("div.er-sheet", { role: "dialog" }, h("div.er-sheet-in",
      h("div.er-sheet-head", h("span.er-sheet-ic", r.obj), h("div.grow", h("b", I18N.tr(r.obj_name)), h("br"),
        h("small.muted", lv[0], " ", I18N.tr(r.name))), h("button.icon-btn", { "aria-label": T("Close"), onclick: closeIt }, "✕")),
      ...body, foot, hints));
  }

  function peekBox(r) {
    const on = r.show && r.show.length;
    return h("div.er-peek", on ? h("small.muted", "👀 ", T("Remember it!"))
      : h("button.btn.er-look", { onclick: () => act("peek", { key: r.key }) }, "👀 ", T("Peek")));
  }

  function doorSheet(rm, closeIt) {
    const d = rm.door;
    const lines = d.kind === "order" ? [I18N.tr(T("The lock needs the digits in this order:")), h("div.er-big", d.order.join("  "))]
      : d.kind === "sum" ? [I18N.tr(T("The code is the sum of all the numbers you found in this room."))]
        : [I18N.tr(T("Press the gems in the order of their numbers (#1 first)."))];
    const inp = d.kind === "colours"
      ? orderInput("door", (d.colours || []).map(c => ({ ...c, v: "💎" })), d.n, false, true, a => submit(null, a))
      : keypad("door", d.kind === "order" ? d.n : 3, a => submit(null, a));
    return h("div.er-sheet", { role: "dialog" }, h("div.er-sheet-in",
      h("div.er-sheet-head", h("span.er-sheet-ic", "🚪"), h("div.grow", h("b", T("Exit door"))), h("button.icon-btn", { "aria-label": T("Close"), onclick: closeIt }, "✕")),
      h("div.er-lines", ...lines.map(x => typeof x === "string" ? h("p", x) : x)),
      h("div.er-frags.big", ...rm.riddles.map(r => h("span.er-fragbox", h("small", r.obj), fragView(r.frag, d.kind)))),
      rm.riddles.some(r => !r.solved) ? h("p.small.muted", "🔎 ", T("Not all parts found yet – solve the riddles in the room!")) : null,
      inp));
  }

  // ---------- what a riddle shows
  function block(b) {
    const k = b.k;
    if (k === "big") return h("div.er-big", { translate: "no" }, erVal(b.v));
    if (k === "emo") return h("div.er-emo-wrap", b.label ? h("small.muted", I18N.tr(b.label.t)) : null,
      h("div.er-emo" + (b.tiles ? ".tiles" : ""), { style: { "--cols": b.cols } }, ...b.v.map(x => h("span", x || " "))));
    if (k === "rows") return h("table.er-rows", h("tr", ...(b.head || []).map(x => h("th", x))), ...b.v.map(r => h("tr", ...r.map(x => h("td", x)))));
    if (k === "clock") return clockSvg(b.h, b.m);
    if (k === "grid") return h("div.er-grid" + (b.box ? ".boxed" : ""), { style: { "--cols": b.n } }, ...b.v.map(x => h("span" + (x === "" ? ".empty" : /\d/.test(x) ? "" : ".star"), x)));
    if (k === "pyr") return h("div.er-pyr", ...b.v.map(row => h("div", ...row.map(x => h("span" + (x === "" ? ".empty" : /\d/.test(x) ? "" : ".star"), x)))));
    if (k === "dice") return h("div.er-dice", ...b.v.map(n => diceSvg(n)));
    if (k === "coins") return h("div.er-coins", ...b.v.map(n => h("span.er-coin.c" + n, String(n))));
    if (k === "shapes") return h("div.er-shapes", ...b.v.map(n => shapeSvg(n)));
    if (k === "seq") return h("div.er-seq" + (b.plain ? ".plain" : ""), ...b.v.flatMap((x, i) => [i && !b.plain ? h("i", "→") : null, h("span" + (x === "?" ? ".q" : ""), x)]).filter(Boolean));
    if (k === "towers") return h("div.er-towers", ...b.v.map(n => h("div.er-tower", ...Array.from({ length: n }, () => h("i")))), h("div.er-tower.q", "?"));
    if (k === "eqs") return h("div.er-eqs", ...b.v.map(([a, c]) => h("p", a, " = ", h("b", c))));
    if (k === "key") return h("div.er-key", ...erVal(b.v).map(([s, l]) => h("span", h("b", s), " = ", l)));
    if (k === "letters") return h("div.er-letters", { style: { "--cols": b.n } }, ...erVal(b.v).map(x => h("span", x)));
    if (k === "abc") return h("div.er-abc", ..."ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("").map((c, i) => h("span", c, b.num ? h("small", String(i + 1)) : null)));
    if (k === "mirror") return h("div.er-mirror", "🪞");
    if (k === "compass") return h("div.er-compass", h("span.n", "⬆️ ", T("North")), h("span.e", "➡️ ", T("East")), h("span.s", "⬇️ ", T("South")), h("span.w", "⬅️ ", T("West")), h("b", "🧭"));
    if (k === "gems") return h("div.er-gems", ...b.v.map((c, i) => h("i.er-gem.big.flash", { style: { background: c.c, animationDelay: (i * 0.7) + "s" }, title: I18N.tr(c.t) })));
    if (k === "ladder") return ladderSvg(b);
    if (k === "gears") return h("div.er-gears", ...Array.from({ length: b.n }, (_, i) => h("span.er-gear" + (b.mark === i + 1 ? ".mark" : ""),
      h("b", "⚙️"), h("small", b.labels ? b.labels[i] : (i === 0 ? "1 ↻" : b.mark === i + 1 ? (i + 1) + " ?" : String(i + 1))))));
    return null;
  }

  const svg = (w, hgt, inner, cls = "") => h("span.er-svg" + cls, { html: `<svg viewBox="0 0 ${w} ${hgt}" aria-hidden="true">${inner}</svg>` });
  function clockSvg(hh, mm) {
    const a = (mm / 60) * 360, b = ((hh % 12) / 12) * 360 + mm / 2;
    const hand = (deg, len, wdt) => { const r = (deg - 90) * Math.PI / 180; return `<line x1="50" y1="50" x2="${50 + len * Math.cos(r)}" y2="${50 + len * Math.sin(r)}" stroke-width="${wdt}" stroke-linecap="round"/>`; };
    let ticks = "";
    for (let i = 1; i <= 12; i++) { const r = (i * 30 - 90) * Math.PI / 180; ticks += `<text x="${50 + 37 * Math.cos(r)}" y="${50 + 37 * Math.sin(r) + 4}" text-anchor="middle" font-size="10">${i}</text>`; }
    return svg(100, 100, `<circle cx="50" cy="50" r="46" class="face"/>${ticks}<g class="hands">${hand(b, 22, 5)}${hand(a, 34, 3)}</g><circle cx="50" cy="50" r="3"/>`, ".er-clockface");
  }
  function diceSvg(n) {
    const P = { 1: [[50, 50]], 2: [[28, 28], [72, 72]], 3: [[28, 28], [50, 50], [72, 72]], 4: [[28, 28], [72, 28], [28, 72], [72, 72]],
      5: [[28, 28], [72, 28], [50, 50], [28, 72], [72, 72]], 6: [[28, 25], [72, 25], [28, 50], [72, 50], [28, 75], [72, 75]] }[n] || [];
    return svg(100, 100, `<rect x="5" y="5" width="90" height="90" rx="16" class="die"/>${P.map(([x, y]) => `<circle cx="${x}" cy="${y}" r="9"/>`).join("")}`, ".er-die");
  }
  function shapeSvg(n) {
    if (!n) return svg(100, 100, `<circle cx="50" cy="50" r="40" class="shape"/>`, ".er-shape");
    const pts = Array.from({ length: n }, (_, i) => { const r = (i * 360 / n - 90) * Math.PI / 180; return (50 + 42 * Math.cos(r)).toFixed(1) + "," + (54 + 42 * Math.sin(r)).toFixed(1); }).join(" ");
    return svg(100, 100, `<polygon points="${pts}" class="shape"/>`, ".er-shape");
  }
  function ladderSvg(b) {
    const W = 60 * b.n, H = 24 * (b.rows + 1);
    const x = i => 30 + 60 * i;
    let s = "";
    for (let i = 0; i < b.n; i++) s += `<line x1="${x(i)}" y1="0" x2="${x(i)}" y2="${H}"/>`;
    for (const [y, i] of b.rungs) s += `<line x1="${x(i)}" y1="${24 * (y + 1)}" x2="${x(i + 1)}" y2="${24 * (y + 1)}"/>`;
    return h("div.er-ladder", { style: { "--n": b.n } }, h("div.er-lad-row", ...b.top.map(t => h("span", t))), svg(W, H, `<g class="lad">${s}</g>`, ".er-lad"),
      h("div.er-lad-row", ...b.bottom.map(t => h("span", t))));
  }

  // ---------- how a riddle is answered
  function input(r) {
    const i = r.input, k = i.k, send = a => submit(r.key, a);
    if (k === "num") return keypad(r.key, i.max, send);
    if (k === "text") {
      const inp = h("input.er-text", { type: "text", value: draft[r.key] || "", autocomplete: "off", autocapitalize: "characters", spellcheck: false,
        placeholder: I18N.tr(T("Your answer")), oninput: e => { draft[r.key] = e.target.value; }, onkeydown: e => { if (e.key === "Enter" && inp.value.trim()) send(inp.value.trim()); } });
      return h("div.er-answer", inp, h("button.btn", { onclick: () => inp.value.trim() && send(inp.value.trim()) }, "🔓 ", T("Try")));
    }
    if (k === "choice") return choiceInput(r, send);
    if (k === "cells") return cellsInput(r, send);
    if (k === "order") return orderInput(r.key, i.opts, i.len, !!i.repeat, !!i.gems, send);
    if (k === "lights") return lightsInput(r, send);
    if (k === "slide") return slideInput(r, send);
    if (k === "rings") return ringsInput(r, send);
    if (k === "pipes") return pipesInput(r, send);
    if (k === "levers") return leversInput(r, send);
    return null;
  }

  function keypad(key, max, send) {
    const disp = h("div.er-display", { translate: "no" });
    const shown = () => { const v = draft[key] || ""; disp.textContent = v ? v.split("").join(" ") : "_ ".repeat(Math.min(max, 6)).trim(); };
    shown();
    const press = d => { const v = draft[key] || ""; if (v.length < max) { draft[key] = v + d; shown(); } };
    const keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "⌫", "0", "✓"].map(x => h("button.er-key-btn" + (x === "✓" ? ".go" : ""), { onclick: () => {
      if (x === "⌫") { draft[key] = (draft[key] || "").slice(0, -1); shown(); }
      else if (x === "✓") { if (draft[key]) send(draft[key]); }
      else press(x);
    } }, x));
    return h("div.er-keypad-wrap", disp, h("div.er-keypad", ...keys));
  }

  const optView = o => [o.pair ? h("span.er-pair", ...o.pair.map(c => h("i.er-gem", { style: { background: c.c } })))
    : o.c && !o.v ? h("i.er-gem", { style: { background: o.c } }) : h("span.er-opt-v", o.c ? { style: { "--c": o.c } } : {}, o.v || ""),
  o.pair ? h("small", I18N.tr(o.pair[0].t) + " + " + I18N.tr(o.pair[1].t)) : o.t ? h("small", I18N.tr(o.t)) : null];

  function choiceInput(r, send) {
    const i = r.input;
    const sel = draft[r.key];
    const grid = h("div.er-choice" + (i.books ? ".books" : ""), { style: { "--cols": i.cols || 2 } }, ...i.opts.map((o, n) =>
      h("button.er-opt" + (sel === n ? ".on" : "") + (o.c ? ".col" : ""), { style: o.c ? { "--c": o.c } : {}, onclick: () => { draft[r.key] = n; draw(true); } },
        i.books ? h("span.er-book", { style: { background: o.c } }) : optView(o))));
    return h("div.er-answer.col", grid, h("button.btn", { disabled: sel == null, onclick: () => send(draft[r.key]) }, "🔓 ", T("Try")));
  }

  function cellsInput(r, send) {
    const i = r.input, multi = i.multi || 0;
    let sel = draft[r.key];
    if (multi && !Array.isArray(sel)) sel = draft[r.key] = [];
    const isOn = n => multi ? sel.includes(n) : sel === n;
    const grid = h("div.er-cells" + (i.map ? ".map" : ""), { style: { "--cols": i.cols } }, ...i.v.map((x, n) => h("button.er-cell" + (isOn(n) ? ".on" : ""), { onclick: () => {
      if (multi) { const s = new Set(sel); s.has(n) ? s.delete(n) : (s.size < multi && s.add(n)); draft[r.key] = [...s]; }
      else draft[r.key] = n;
      draw(true);
    } }, x || " ")));
    const ready = multi ? sel.length === multi : sel != null;
    return h("div.er-answer.col", i.label ? h("small.muted", I18N.tr(i.label.t)) : null, grid,
      h("button.btn", { disabled: !ready, onclick: () => send(draft[r.key]) }, "🔓 ", T("Try"), multi ? " (" + sel.length + "/" + multi + ")" : ""));
  }

  function orderInput(key, opts, len, repeat, gems, send) {
    const seq = Array.isArray(draft[key]) ? draft[key] : (draft[key] = []);
    const row = h("div.er-ordered", ...Array.from({ length: len }, (_, n) => {
      const o = opts[seq[n]];
      return h("span.er-slot" + (o ? ".on" : ""), o ? (gems ? h("i.er-gem", { style: { background: o.c } }) : o.v) : String(n + 1));
    }));
    const btns = h("div.er-choice", { style: { "--cols": Math.min(opts.length, 6) } }, ...opts.map((o, n) => h("button.er-opt" + (gems ? ".gem" : ""), {
      disabled: seq.length >= len || (!repeat && seq.includes(n)), onclick: () => { seq.push(n); draw(true); } },
    gems ? h("i.er-gem.big", { style: { background: o.c }, title: I18N.tr(o.t || "") }) : optView(o))));
    return h("div.er-answer.col", row, btns, h("div.row.center",
      h("button.btn.ghost", { disabled: !seq.length, onclick: () => { seq.pop(); draw(true); } }, "⌫"),
      h("button.btn", { disabled: seq.length !== len, onclick: () => send([...seq]) }, "🔓 ", T("Try"))));
  }

  // mechanical puzzles: played here, the moves go to the server when the puzzle looks solved (or on «Check»)
  const resetBtn = (key, fresh) => h("button.btn.ghost.small", { onclick: () => { local[key] = fresh(); draw(true); } }, "↺ ", T("Start again"));

  function lightsInput(r, send) {
    const n = r.input.n;
    const s = local[r.key] || (local[r.key] = { on: [...r.input.on], moves: [] });
    const press = i => {
      const rr = Math.floor(i / n), cc = i % n;
      for (const [dr, dc] of [[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]]) { const a = rr + dr, b = cc + dc; if (a >= 0 && a < n && b >= 0 && b < n) s.on[a * n + b] ^= 1; }
      s.moves.push(i);
      if (!s.on.some(Boolean)) send([...s.moves]); else draw(true);
    };
    return h("div.er-answer.col", h("div.er-lights", { style: { "--cols": n } }, ...s.on.map((v, i) => h("button.er-lamp" + (v ? ".on" : ""), { "aria-label": v ? "on" : "off", onclick: () => press(i) }, v ? "🔆" : "⚫"))),
      resetBtn(r.key, () => ({ on: [...r.input.on], moves: [] })));
  }

  function slideInput(r, send) {
    const n = r.input.n;
    const s = local[r.key] || (local[r.key] = { v: [...r.input.v], moves: [] });
    const move = i => {
      const b = s.v.indexOf(0);
      if (Math.abs(Math.floor(i / n) - Math.floor(b / n)) + Math.abs(i % n - b % n) !== 1) return;
      s.moves.push(s.v[i]); s.v[b] = s.v[i]; s.v[i] = 0;
      if (s.v.every((x, k) => x === (k + 1) % (n * n))) send([...s.moves]); else draw(true);
    };
    return h("div.er-answer.col", h("div.er-slide", { style: { "--cols": n } }, ...s.v.map((x, i) => h("button.er-tile" + (x ? "" : ".gap"), { onclick: () => move(i) }, x ? String(x) : ""))),
      h("small.muted", I18N.tr(T("Moves: {0}")).replace("{0}", s.moves.length)), resetBtn(r.key, () => ({ v: [...r.input.v], moves: [] })));
  }

  function ringsInput(r, send) {
    const rs = r.input.rings, tgt = r.target || [];
    const s = local[r.key] || (local[r.key] = { p: rs.map(() => 0), moves: [] });
    const off = i => (s.p[i] + (i ? s.p[i - 1] : 0)) % 6;
    const turn = i => { s.p[i]++; s.moves.push(i); if (rs.every((ring, k) => ring[off(k)] === tgt[k])) send([...s.moves]); else draw(true); };
    return h("div.er-answer.col", h("div.er-rings", ...rs.map((ring, i) => h("div.er-ring" + (ring[off(i)] === tgt[i] ? ".ok" : ""),
      h("span.er-ring-side", ring[(off(i) + 5) % 6]), h("b.er-ring-top", ring[off(i)]), h("span.er-ring-side", ring[(off(i) + 1) % 6]),
      h("span.er-ring-goal", "🎯 ", tgt[i]),
      h("button.btn.small", { onclick: () => turn(i) }, "⟳ ", String(i + 1))))),
    resetBtn(r.key, () => ({ p: rs.map(() => 0), moves: [] })));
  }

  const PIPE_OPEN = { I: [0, 2], L: [0, 1], T: [0, 1, 2] };
  const pipeOpen = (kind, rot) => PIPE_OPEN[kind].map(d => (d + rot) % 4);
  function pipeFlow(n, tiles, src) {
    const wet = new Set();
    if (!pipeOpen(...tiles[src * n]).includes(3)) return wet;
    const todo = [src * n]; wet.add(src * n);
    while (todo.length) {
      const i = todo.pop(), rr = Math.floor(i / n), cc = i % n, op = pipeOpen(...tiles[i]);
      [[-1, 0], [0, 1], [1, 0], [0, -1]].forEach(([dr, dc], d) => {
        const a = rr + dr, b = cc + dc;
        if (!op.includes(d) || a < 0 || a >= n || b < 0 || b >= n) return;
        const j = a * n + b;
        if (!wet.has(j) && pipeOpen(...tiles[j]).includes((d + 2) % 4)) { wet.add(j); todo.push(j); }
      });
    }
    return wet;
  }
  function pipeSvg(kind, rot, wet) {
    const arm = d => ["M50 50V0", "M50 50H100", "M50 50V100", "M50 50H0"][d];
    const path = pipeOpen(kind, rot).map(arm).join(" ");
    return `<svg viewBox="0 0 100 100" aria-hidden="true"><path d="${path}" class="pipe${wet ? " wet" : ""}"/><circle cx="50" cy="50" r="13" class="pipe-joint${wet ? " wet" : ""}"/></svg>`;
  }
  function pipesInput(r, send) {
    const i = r.input, n = i.n;
    const s = local[r.key] || (local[r.key] = { rot: i.v.map(t => t[1]) });
    const tiles = i.v.map((t, k) => [t[0], s.rot[k]]);
    const wet = pipeFlow(n, tiles, i.src);
    const end = i.dst * n + n - 1;
    const done = wet.has(end) && pipeOpen(...tiles[end]).includes(1);
    const grid = h("div.er-pipes", { style: { "--cols": n } }, ...tiles.map((t, k) => h("button.er-pipe", { onclick: () => { s.rot[k] = (s.rot[k] + 1) % 4; draw(true); }, html: pipeSvg(t[0], t[1], wet.has(k)) })));
    const side = (row, ic) => h("div.er-pipe-side", { style: { "--cols": n } }, ...Array.from({ length: n }, (_, k) => h("span", k === row ? ic : "")));
    return h("div.er-answer.col", h("div.er-pipe-wrap", side(i.src, "💧"), grid, side(i.dst, "🪣")),
      h("button.btn", { onclick: () => send([...s.rot]) }, done ? "💧 " : "🔓 ", T("Check")), resetBtn(r.key, () => ({ rot: i.v.map(t => t[1]) })));
  }

  function leversInput(r, send) {
    const i = r.input;
    const s = local[r.key] || (local[r.key] = { pulled: [] });
    const on = [...i.on];
    s.pulled.forEach(l => i.levers[l].forEach(j => { on[j] ^= 1; }));
    const flip = l => { s.pulled = s.pulled.includes(l) ? s.pulled.filter(x => x !== l) : [...s.pulled, l]; draw(true); };
    const all = on.every(Boolean);
    return h("div.er-answer.col", h("div.er-lamps", ...on.map((v, j) => h("span.er-lampi" + (v ? ".on" : ""), v ? "💡" : "⚫", h("small", String(j + 1))))),
      h("div.er-levers", ...i.levers.map((ls, l) => h("button.er-lever" + (s.pulled.includes(l) ? ".down" : ""), { onclick: () => flip(l) },
        h("b", s.pulled.includes(l) ? "⬇️" : "⬆️"), h("span", String.fromCharCode(65 + l)), h("small", "→ " + ls.map(j => j + 1).join(", "))))),
      h("button.btn" + (all ? ".good" : ""), { onclick: () => send([...s.pulled]) }, "🔓 ", T("Check")));
  }

  // ---------- the end
  function result() {
    clearInterval(tick);
    const res = st.result || {}, won = st.winners || [];
    const mine = st.my_team || "0";
    if (won.includes(mine) && !cheered && st.joined) { cheered = true; confetti(); try { Sound.play("done"); } catch {} }
    const title = !won.length ? (st.complete ? T("The time is up – nobody escaped.") : T("The game was ended."))
      : st.teams ? I18N.tr(T("{0} escaped first and wins!")).replace("{0}", erTeam(won[0])) : T("You escaped – well done!");
    const row = k => {
      const x = res[k] || {};
      return h("div.er-res" + (won.includes(k) ? ".win" : ""), st.teams ? h("b", erTeam(k)) : null,
        h("div.er-res-nums", h("span", x.out ? "🎉 " : "🚪 ", (x.rooms || 0) + "/" + st.n_rooms), h("span", "🧩 ", String(x.riddles || 0)),
          h("span", "⏱ ", erClock(x.time || 0)), h("span", "💡 ", String(x.hints || 0)), h("span", "⭐ ", String(x.score || 0))));
    };
    return h("section.card.center.pj-result.er-result", h("h2", won.length ? "🏆 " : "🔒 ", I18N.tr(title)),
      ...Object.keys(res).sort().map(row),
      h("p.small.muted", I18N.tr(T("⏱ = time with {0} s per hint and {1} s per wrong answer")).replace("{0}", st.hint_s).replace("{1}", st.wrong_s)),
      h("ol.pk-rank", ...st.players.map(p => h("li" + (p.id === myId ? ".vw-me" : ""), avatarSvg(p.avatar || {}, 30),
        h("span.grow", C(p.name, "strong"), st.teams && p.team ? h("small.muted", " " + ER_TEAMS[+p.team]) : null),
        p.coins ? h("b.pj-plus", "+" + p.coins + " 🪙") : null))),
      st.coins_on ? null : h("p.small.muted", T("Coins only at a table with at least two people of the family – not for guests.")),
      h("div.row.center", h("button.btn", { onclick: back }, T("Back"))));
  }
  poll();
}

async function escapeView() {
  const box = h("div.er-live");
  screen("games", box);
  escapeLive(box, S.profile, () => go("games"));
}

async function escapeFamilyCard() {
  const c = S.me && S.me.community, g = c && c.escape;
  return h("section.card.quiz-card", h("h2", ER_ICON, " ", erName()),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("escape") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("Solve riddles together and find the way out of every room – all together or in two teams.")),
         h("button.btn", { onclick: () => escapeStartDialog(() => go("escape")) }, "👨‍👩‍👧 ", T("Open a family table"))]);
}
