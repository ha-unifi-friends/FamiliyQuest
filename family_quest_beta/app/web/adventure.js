// ---------------------------------------------------------------- 🗝️ Adventure games (familyquest/adventuregame.py)
// Point & click games on the family bookshelf (stories.js: shelf, visibility, approval, pictures upload, painter).
// gamePlayer() plays a game – the engine runs on the server (agServerEngine: the published game, saved per player;
// agTryEngine: ▶ the working copy from any room, nothing saved). gameEditor() builds one: room map, rooms with hotspots
// drawn on the picture, items / switches / endings, dialogues, use and combine rules, the live checker of the server.
"use strict";

const AG_MAX = { rooms: 40, spots: 30, items: 60, flags: 100, lines: 200, answers: 6, rules: 200, endings: 20, actions: 8, cond: 4, variants: 3 };
// own SVG pictures (adventuregame.py ASSETS / ROOMS, web/img/adventure)
const AG_ASSETS = () => ({ door: T("Wooden door"), door_arch: T("Stone gate"), door_metal: T("Metal door"), hatch: T("Hatch"), window: T("Window"),
  key: T("Key"), chest: T("Chest"), lever: T("Lever"), lamp: T("Lamp"), candle: T("Candle"), book: T("Book"), potion: T("Potion"), rope: T("Rope"),
  stick: T("Stick"), ladder: T("Ladder"), crystal: T("Crystal"), magnet: T("Magnet"), battery: T("Battery"), cable: T("Cable"), card: T("Key card"),
  button: T("Button"), screen: T("Screen"), cauldron: T("Cauldron"), bookshelf: T("Bookshelf"), table: T("Table"), bed: T("Bed"), box: T("Box"),
  plant: T("Plant"), well: T("Well"), wand: T("Magic wand"), wizard: T("Wizard"), robot: T("Robot"), cat: T("Cat"), dragon: T("Dragon"),
  ghost: T("Ghost"), knight: T("Knight"), pirate: T("Pirate"), alien: T("Alien"), owl: T("Owl") });
const AG_ROOMS = () => ({ tower: T("Tower room"), library: T("Library"), hall: T("Stone hall"), hallway: T("Hallway"), cabin: T("Spaceship cabin"),
  corridor: T("Spaceship corridor"), bridge: T("Spaceship bridge"), engine: T("Engine room"), storage: T("Storage room"), dark: T("Dark room") });
const AG_KINDS = () => ({ door: ["🚪", T("Door")], object: ["📦", T("Object")], person: ["🧙", T("Character")] });
const AG_VERBS = () => ({ look: ["👁️", T("Look at")], take: ["✋", T("Take")], talk: ["💬", T("Talk")], go: ["🚪", T("Go through")], use: ["🔧", T("Use")] });
// messages of the engine that are codes (adventuregame.py CODE_TEXT)
const AG_CODES = { nothing: T("Nothing special."), locked: T("It is locked."), no_use: T("That does not work."),
  no_combine: T("These two things do not fit together."), got: T("You get: {0}") };
const AG_ACTS = () => ({ say: ["💬", T("Show a text")], give: ["🎁", T("Give item")], take: ["➖", T("Take item away")], set: ["🟢", T("Switch on")],
  clear: ["⚪", T("Switch off")], go: ["🚪", T("Go to room")], end: ["🏁", T("End the game")] });

const agAssetUrl = k => "img/adventure/" + k + ".svg";
const agBgUrl = k => (k in AG_ROOMS() ? agAssetUrl(k) : sbBgUrl(k));
const agMsg = m => m.t != null ? m.t : sbFmt(AG_CODES[m.c] || "…", ...(m.a || []));

// a picture of a hotspot or an item: asset, emoji, own drawing (SVG of svgpaint.js, or an older PNG) / photo – always as an <img>
function agArt(p, cls = "") {
  if (!p) return null;
  if (p.k === "asset") return h("img.ag-art" + cls, { src: agAssetUrl(p.v), alt: "", draggable: false });
  if (p.k === "emoji") return h("span.ag-emo" + cls, { translate: "no", "aria-hidden": "true" }, p.v);
  if (p.k === "img") return h("img.ag-art" + cls, { src: sbImg(p.v), alt: "", draggable: false, loading: "lazy" });
  if (p.k === "svg") return h("img.ag-art" + cls, { src: svgDataUrl(p.v), alt: "", draggable: false });
  return null;
}
// the picture of a room (fills the 4:3 scene)
function agBg(p) {
  if (!p) return h("div.ag-bg.none");
  if (p.k === "lib") return h("img.ag-bg", { src: agBgUrl(p.v), alt: "", draggable: false });
  if (p.k === "img") return h("img.ag-bg", { src: sbImg(p.v), alt: "", draggable: false });
  if (p.k === "svg") return h("img.ag-bg", { src: svgDataUrl(p.v), alt: "", draggable: false });
  return h("div.ag-bg.none");
}
const agItemLabel = it => h("span.ag-ilabel", it.icon ? agArt(it.icon, ".ag-iicon") : h("span.ag-emo.ag-iicon", "🎒"), C(it.name || "…", "span.ag-iname"));

// ---------------------------------------------------------------- playing
function agServerEngine(id) {
  const lang = "?lang=" + encodeURIComponent(sbAppLang());
  return { read: () => api(`stories/${id}/read${lang}`), act: mv => api(`stories/${id}/read/act`, { method: "POST", body: mv }),
    restart: () => api(`stories/${id}/read/restart${lang}`, { method: "POST" }), rate: n => api(`stories/${id}/rate`, { method: "POST", body: { stars: n } }) };
}

// ▶ the working copy (editor) or a game waiting for approval (👀 parents): the state travels with every move
function agTryEngine(id, { room = null, pending = false } = {}) {
  let state = null;
  const run = async body => { const r = await api(`stories/${id}/try`, { method: "POST", body: { ...body, pending } }); state = r.state; return r; };
  return { read: () => run({ room }), act: mv => run({ state, move: mv }), restart: () => run({ room }), rate: async () => {} };
}

function gamePlayer(engine, { onClose = null, preview = false } = {}) {
  const full = h("div.quiz-full.sb-full.ag-full.ag-player");
  let st = null, busy = false, closed = false, sel = null, pick = null, msgs = [], roomId = null;
  const close = () => {
    if (closed) return; closed = true;
    full.remove(); window.removeEventListener("hashchange", close);
    if (!document.querySelector(".sb-full")) document.body.classList.remove("quiz-open");
    onClose && onClose();
  };
  window.addEventListener("hashchange", close);
  const run = async (fn, mv = null) => {
    if (busy) return; busy = true;
    try {
      const r = await fn();
      const moved = st && r.room.id !== st.room.id;
      st = r; msgs = r.msgs || []; sel = null;
      if (pick && !st.inv.some(i => i.id === pick)) pick = null;
      if (mv) pick = null;                                   // after a move the item goes back into the backpack
      draw(moved);
      if (st.end) { if (st.end.kind === "win") { Sound.play("done"); confetti(full); } else Sound.play("wrong"); }
      else if (moved) Sound.play("tap");
    } catch (e) { toast(e.message, "bad"); } finally { busy = false; }
  };
  const move = mv => run(() => engine.act(mv), mv);
  const restart = () => { pick = null; run(() => engine.restart()); };
  const tapSpot = s => {
    if (st.talk || st.end) return;
    if (pick) return move({ verb: "use", spot: s.id, item: pick });
    sel = sel === s.id ? null : s.id; draw(false);
  };
  const tapItem = it => {
    if (st.talk || st.end) return;
    if (pick && pick !== it.id) return move({ verb: "combine", item: pick, item2: it.id });
    pick = pick === it.id ? null : it.id; sel = null; draw(false);
  };
  let hint = 0;
  const showAll = () => { full.classList.add("ag-hint"); clearTimeout(hint); hint = setTimeout(() => full.classList.remove("ag-hint"), 1600); };
  const scene = () => h("div.ag-scene", { lang: st.lang },
    agBg(st.room.bg),
    ...st.spots.map(s => h("button.ag-spot.k-" + s.kind + (s.art ? ".art" : "") + (sel === s.id ? ".on" : "") + (pick ? ".target" : ""),
      { type: "button", title: s.name, "aria-label": s.name, "data-id": s.id, style: { left: s.x + "%", top: s.y + "%", width: s.w + "%", height: s.h + "%" }, onclick: () => tapSpot(s) },
      agArt(s.art))),
    h("button.ag-lens", { type: "button", title: T("Show everything you can tap"), "aria-label": T("Show everything you can tap"), onclick: showAll }, "🔍"));
  const panel = () => {
    const spot = st.spots.find(s => s.id === sel), item = st.inv.find(i => i.id === pick), V = AG_VERBS();
    return h("div.ag-panel", { lang: st.lang },
      spot ? h("div.ag-verbs", h("b.ag-vname", (AG_KINDS()[spot.kind] || [""])[0], " ", C(spot.name)),
        h("div.ag-vbtns", ...spot.verbs.map(v => h("button.btn.small.ag-verb", { onclick: () => move({ verb: v, spot: spot.id }) }, h("span", { translate: "no" }, V[v][0]), " ", V[v][1])),
          h("button.icon-btn.ag-vx", { title: T("Close"), "aria-label": T("Close"), onclick: () => { sel = null; draw(false); } }, "✕")))
        : item ? h("div.ag-verbs.use", h("span", "🔧 ", sbFmt(T("Use «{0}» with …"), "⁨" + item.name + "⁩")), h("span.small.muted", T("Tap a thing in the room or another item.")),
          h("button.icon-btn.ag-vx", { title: T("Cancel"), "aria-label": T("Cancel"), onclick: () => { pick = null; draw(false); } }, "✕")) : null,
      msgs.length ? h("div.ag-msgs", ...msgs.map(m => h("p.ag-msg", m.c === "got" ? "🎒 " : "", agMsg(m)))) : null,
      h("div.ag-room", C(st.room.name, "b.ag-rname"), C(st.room.text, "p.ag-rtext")));
  };
  const inv = () => h("div.ag-inv", { role: "list", "aria-label": T("Backpack") },
    h("span.ag-invic", { "aria-hidden": "true" }, "🎒"),
    st.inv.length ? st.inv.map(it => h("button.ag-item" + (pick === it.id ? ".on" : ""), { type: "button", role: "listitem", title: it.name, onclick: () => tapItem(it) },
      it.icon ? agArt(it.icon, ".ag-iicon") : h("span.ag-emo.ag-iicon", "❔"), C(it.name, "span.ag-iname")))
      : h("span.small.muted.ag-invnone", T("Nothing in the backpack yet")));
  const talk = () => h("div.ag-talk", { lang: st.lang },
    h("div.ag-twho", h("span.ag-tpic", agArt(st.talk.spot.art) || h("span.ag-emo", "🧙")), C(st.talk.spot.name, "b")),
    C(st.talk.line.text, "p.ag-tline"),
    h("div.ag-answers", ...st.talk.answers.map(a => h("button.ag-answer", { onclick: () => move({ verb: "answer", answer: a.i }) }, "💬 ", C(a.t || "…"))),
      h("button.ag-answer.leave", { onclick: () => move({ verb: "leave" }) }, "👋 ", T("Leave"))));
  const ending = () => {
    const win = st.end.kind === "win";
    return h("div.ag-end" + (win ? ".win" : ".lose"), h("div.ag-endbox", { lang: st.lang },
      h("div.ag-endic", win ? "🏆" : "💀"), h("p.ag-endtag", win ? T("You made it!") : T("Oh no!")),
      msgs.length ? h("div.ag-endmsgs", ...msgs.map(m => h("p", agMsg(m)))) : null,
      C(st.end.text, "p.ag-endtext"),
      st.new_ending ? h("p.ag-newend", "✨ ", T("New ending found!")) : null,
      h("p.sb-count", "🏁 ", sbFmt(T("{0} of {1} endings found"), st.found, st.endings)),
      st.may_rate ? h("div.sb-rateme", h("span.small", T("How did you like the game?")),
        h("div.sb-stars", ...[1, 2, 3, 4, 5].map(n => h("button.sb-star" + (n <= (st.rating || 0) ? ".on" : ""), { "aria-label": n + " ★",
          onclick: async () => { try { await engine.rate(n); st.rating = n; draw(false); toast(T("Thank you!"), "good"); } catch (e) { toast(e.message, "bad"); } } }, "★")))) : null,
      h("div.row.center.wrap", h("button.btn", { onclick: restart }, "↺ ", win ? T("Play again") : T("Try again")),
        h("button.btn.ghost", { onclick: close }, "📚 ", T("Back to the bookshelf")))));
  };
  const draw = moved => {
    sbSet(full,
      h("div.sb-rtop.ag-top",
        h("button.icon-btn", { title: T("Close"), "aria-label": T("Close"), onclick: close }, "✕"),
        h("div.sb-rtitle", h("span", { translate: "no" }, st.emoji), C(st.title, "strong")),
        h("span.sb-pill", { title: T("Endings found") }, "🏁 ", st.found + "/" + st.endings),
        !st.fresh ? h("button.icon-btn", { title: T("Start again"), "aria-label": T("Start again"), onclick: async () => (await confirmDialog(I18N.tr(T("Start the game again from the beginning?")))) && restart() }, "↺") : null),
      preview ? h("p.sb-try.small.ag-try", "👀 ", T("Try-out – nothing is saved")) : null,
      h("div.ag-stage" + (moved ? ".enter" : ""), scene()),
      st.talk ? talk() : [panel(), inv()],
      st.end ? ending() : null);
    roomId = st.room.id;
  };
  document.body.append(full);
  document.body.classList.add("quiz-open");
  run(() => engine.read());
}

// ---------------------------------------------------------------- building
async function gameEditor(id, onClose = null) {
  let ed;
  try { ed = await api("stories/" + id); } catch (e) { return toast(e.message, "bad"); }
  const data = ed.data;
  const meta = { title: ed.title, emoji: ed.emoji, color: ed.color, lang: ed.lang };
  let visSent = ed.visibility, mode = "rooms", cur = (data.rooms[0] || {}).id, sel = null, dirty = false, timer = null, saving = null,
    closed = false, showIssues = false, drawing = false, newKind = "object", zoom = null;
  try { mode = localStorage.getItem("fq.ag.mode") || "rooms"; } catch {}
  const full = h("div.quiz-full.sb-full.sb-editor.ag-editor");
  const head = h("div.sb-ehead"), infoEl = h("div.pb-einfo"), checker = h("div.sb-checker"), body = h("div.sb-ebody");
  const stateEl = h("span.sb-state");
  full.append(head, infoEl, checker, body);
  const setState = s => { stateEl.className = "sb-state " + s; stateEl.textContent = { dirty: "●", saving: "…", saved: "✓", error: "⚠" }[s] || "";
    stateEl.title = I18N.tr({ dirty: T("Not saved yet"), saving: T("Saving …"), saved: T("Saved"), error: T("Not saved") }[s] || ""); };
  const save = async () => {
    clearTimeout(timer);
    if (saving) await saving;
    if (!dirty) return true;
    dirty = false; setState("saving");
    const b = { data, ...meta };
    if (visSent !== ed.visibility) b.visibility = visSent;
    saving = api("stories/" + id, { method: "PUT", body: b }).then(r => {
      const vis = r.visibility !== ed.visibility || r.pending !== ed.pending; ed = r; visSent = r.visibility;
      setState(dirty ? "dirty" : "saved"); drawChecker(); if (vis) drawHead(); return true; })
      .catch(e => { dirty = true; setState("error"); toast(e.message, "bad"); return false; }).finally(() => { saving = null; });
    return saving;
  };
  const changed = (redraw = false) => {
    dirty = true; setState("dirty");
    clearTimeout(timer); timer = setTimeout(save, 1200);
    if (redraw) drawBody();
  };
  const finish = () => { window.removeEventListener("hashchange", close); full.remove();
    if (!document.querySelector(".sb-full")) document.body.classList.remove("quiz-open"); onClose && onClose(); };
  const close = async () => { if (closed) return; closed = true; await save(); finish(); };
  window.addEventListener("hashchange", close);

  // ---------- look-ups
  const nextId = list => Math.max(0, ...list.map(x => x.id)) + 1;
  const spots = () => data.rooms.flatMap(r => r.spots.map(s => [s, r]));
  const nextSpot = () => Math.max(0, ...spots().map(([s]) => s.id)) + 1;
  const room = rid => data.rooms.find(r => r.id === rid);
  const nm = (x, fallback = "…") => (x && x.name) || fallback;
  const lineLabel = x => { const t = (x.text || "").replace(/\s+/g, " ").trim(); return "💬 " + (t.length > 28 ? t.slice(0, 27) + "…" : t || "…"); };
  const endLabel = e => (e.kind === "win" ? "🏆 " : "💀 ") + (((e.text || "").slice(0, 26)) || "…");
  const ask = async (msg, value = "") => { const v = await promptDialog(msg, value, { maxLength: 40 }); return v == null ? null : v.trim().slice(0, 40) || null; };
  const newItem = name => { if (data.items.length >= AG_MAX.items) return toast(I18N.tr(T("A game can have at most 60 items")), "bad"), null;
    const it = { id: nextId(data.items), name, icon: null }; data.items.push(it); return it; };
  const newFlag = name => { if (data.flags.length >= AG_MAX.flags) return toast(I18N.tr(T("A game can have at most 100 switches")), "bad"), null;
    const f = { id: nextId(data.flags), name }; data.flags.push(f); return f; };
  const newLine = (text = "") => { if (data.lines.length >= AG_MAX.lines) return toast(I18N.tr(T("A game can have at most 200 dialogue lines")), "bad"), null;
    const l = { id: nextId(data.lines), text, answers: [{ t: "", if: [], do: [], next: null }] }; data.lines.push(l); return l; };
  const newRoom = () => { if (data.rooms.length >= AG_MAX.rooms) return toast(I18N.tr(T("A game can have at most 40 rooms")), "bad"), null;
    const r = { id: nextId(data.rooms), name: "", text: "", bg: { k: "lib", v: "hall" }, variants: [], spots: [] }; data.rooms.push(r);
    if (!data.start) data.start = r.id; return r; };
  const newEnding = kind => { if (data.endings.length >= AG_MAX.endings) return toast(I18N.tr(T("A game can have at most 20 endings")), "bad"), null;
    const e = { id: nextId(data.endings), kind, text: "" }; data.endings.push(e); return e; };
  const flash = sel_ => setTimeout(() => { const el = full.querySelector(sel_); if (el) { el.scrollIntoView({ behavior: "smooth", block: "center" }); el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash"); } }, 60);
  const goTo = (m, then) => { mode = m; try { localStorage.setItem("fq.ag.mode", m); } catch {} drawHead(); drawBody(); then && then(); };
  // removing an item / switch / line / room / ending / hotspot: every reference goes too (the checker would complain)
  const purge = (kind, rid) => {
    const keepCond = c => c.filter(a => !(a.k === kind && a.id === rid));
    const actKinds = { item: ["give", "take"], flag: ["set", "clear"], room: ["go"], end: ["end"] }[kind] || [];
    const keepDo = d => d.filter(a => !(actKinds.includes(a.k) && a.id === rid));
    for (const r of data.rooms) {
      r.variants.forEach(v => { v.if = keepCond(v.if); });
      for (const s of r.spots) {
        s.if = keepCond(s.if); s.lock = keepCond(s.lock);
        if (kind === "item" && s.item === rid) s.item = null;
        if (kind === "room" && s.to === rid) s.to = null;
        if (kind === "end" && s.end === rid) s.end = null;
        if (kind === "line" && s.talk === rid) s.talk = null;
      }
    }
    for (const l of data.lines) l.answers.forEach(a => { a.if = keepCond(a.if); a.do = keepDo(a.do); if (kind === "line" && a.next === rid) a.next = null; });
    data.rules = data.rules.filter(r => !((kind === "item" && (r.item === rid || r.item2 === rid) && r.kind === "combine") || (kind === "spot" && r.spot === rid)));
    data.rules.forEach(r => { r.if = keepCond(r.if); r.do = keepDo(r.do); if (kind === "item" && r.item === rid) r.item = null; });
  };

  // ---------- header, test play, publishing
  const publish = async () => {
    if (!(await save())) return;
    if ((ed.issues || []).some(i => i.level !== "warn")) { showIssues = true; drawChecker(); return toast(I18N.tr(T("Not finished yet – look at the checker")), "bad"); }
    try {
      const r = await api(`stories/${id}/publish`, { method: "POST" });
      if (r.status === "pending") toast(I18N.tr(T("Sent to the parents – they check it first")), "good");
      else { toast(I18N.tr(T("Published! The family can play it now.")), "good"); confetti(full); Sound.play("done"); }
      ed = await api("stories/" + id); drawHead(); drawChecker();
    } catch (e) { toast(e.message, "bad"); }
  };
  const test = async (rid = null) => {
    if (!(await save())) return;
    gamePlayer(agTryEngine(id, { room: rid }), { preview: true });
  };
  const TABS = () => [["map", "🗺️", T("Map")], ["rooms", "🚪", T("Rooms")], ["things", "🎒", T("Things")], ["talk", "💬", T("Dialogues")], ["rules", "⚙️", T("Rules")]];
  const drawHead = () => {
    sbSet(head,
      h("div.sb-erow",
        h("button.icon-btn", { title: T("Close"), "aria-label": T("Close"), onclick: close }, "✕"),
        h("button.sb-etitle", { title: T("Game settings"), onclick: () => metaDialog() },
          h("span.sb-eic", { style: { background: SB_COVERS[meta.color] || SB_COVERS[0] }, translate: "no" }, meta.emoji),
          C(meta.title || "…", "strong"), h("span.sb-pen", "⚙️")),
        stateEl),
      h("div.sb-erow.sb-tools",
        h("div.sb-segs.ag-tabs", ...TABS().map(([k, ic, label]) => h("button.sb-seg" + (mode === k ? ".on" : ""), { title: label, "aria-label": label, onclick: () => goTo(k) },
          h("span", { translate: "no" }, ic), h("span.ag-hide-s", " ", label)))),
        h("span.grow"),
        h("button.btn.small.ghost", { onclick: () => test(), title: T("Test play from the start") }, "▶", h("span.sb-hide-s", " ", T("Test"))),
        h("button.btn.small", { onclick: publish }, "🚀", h("span.ag-hide-s", " ", ed.live && !ed.changed ? T("On the shelf") : ed.pending ? T("Waiting") : T("Publish")))));
    sbSet(infoEl,
      ed.mine ? h("div.sb-erow.sb-visrow", h("b.small", T("Who can play it?")), sbVisPicker(visSent, v => { visSent = v; changed(); save(); }))
        : h("p.sb-note", SB_VIS()[ed.visibility][0], " ", SB_VIS()[ed.visibility][1], " · ", C(ed.author)),
      ed.pending ? h("p.sb-note", "⏳ ", ed.parent ? T("This game waits for a parent's approval (Family › My books).") : T("Your game waits for a parent's approval.")) : null);
  };

  // ---------- checker (the server's – it also plays every way through the game)
  const goIssue = i => {
    if (i.spot) { cur = i.room; sel = i.spot; goTo("rooms", () => flash(".ag-sheet")); }
    else if (i.room) { cur = i.room; sel = null; goTo("rooms", () => flash(".ag-rcard")); }
    else if (i.line) goTo("talk", () => flash("#agl-" + i.line));
    else if (i.rule) goTo("rules", () => flash("#agr-" + i.rule));
    else if (/^(item|flag|ending)/.test(i.code)) goTo("things");
  };
  const drawChecker = () => {
    const list = ed.issues || [], errs = list.filter(i => i.level !== "warn"), warns = list.filter(i => i.level === "warn");
    const li = i => h("li" + (i.level === "warn" ? ".warn" : ""), h("button.link", { onclick: () => goIssue(i) }, i.level === "warn" ? "💡 " : "", sbIssueText(i)));
    sbSet(checker, errs.length
      ? h("details.sb-issues", { open: showIssues, ontoggle: e => { showIssues = e.target.open; } },
          h("summary", "⚠️ ", sbFmt(T("{0} things to finish before publishing"), errs.length)), h("ul", ...errs.map(li), ...warns.map(li)))
      : [h("div.sb-ready", "✅ ", T("Ready to publish – the game can be won.")),
        warns.length ? h("details.sb-issues.ag-warns", h("summary", "💡 ", sbFmt(T("Hints: {0}"), warns.length)), h("ul", ...warns.map(li))) : null]);
  };

  // ---------- small editors: conditions and actions
  const condEditor = (list, onChange, empty = T("always")) => {
    const box = h("div.ag-cond");
    const opts = () => [...data.items.flatMap(it => [[`item:${it.id}:0`, "🎒 " + sbFmt(T("has «{0}»"), nm(it))], [`item:${it.id}:1`, "🎒 " + sbFmt(T("has not «{0}»"), nm(it))]]),
      ...data.flags.flatMap(f => [[`flag:${f.id}:0`, "🟢 " + sbFmt(T("«{0}» is on"), nm(f))], [`flag:${f.id}:1`, "⚪ " + sbFmt(T("«{0}» is off"), nm(f))]])];
    const draw = () => sbSet(box,
      list.length ? null : h("span.small.muted.ag-always", empty),
      ...list.map((a, i) => {
        const sel_ = h("select.ag-csel", { "aria-label": T("Condition") }, ...opts().map(([v, l]) => h("option", { value: v, selected: v === `${a.k}:${a.id}:${a.not ? 1 : 0}`, translate: "no" }, l)),
          !opts().some(([v]) => v === `${a.k}:${a.id}:${a.not ? 1 : 0}`) ? h("option", { selected: true, value: "" }, "⚠️ ", T("deleted")) : null,
          h("option", { value: "new:item" }, "＋ ", T("New item …")), h("option", { value: "new:flag" }, "＋ ", T("New switch …")));
        sel_.onchange = async () => {
          let v = sel_.value;
          if (v.startsWith("new:")) {
            const name = (await ask(v === "new:item" ? T("Name of the new item") : T("Name of the new switch")));
            const x = name && (v === "new:item" ? newItem(name) : newFlag(name));
            if (!x) return draw();
            v = `${v.slice(4)}:${x.id}:0`;
          }
          const [k, rid, not] = v.split(":"); list[i] = { k, id: +rid, not: not === "1" }; onChange(); draw();
        };
        return h("div.ag-crow", sel_, h("button.icon-btn.ag-x", { title: T("Remove"), "aria-label": T("Remove"), onclick: () => { list.splice(i, 1); onChange(); draw(); } }, "✕"));
      }),
      list.length < AG_MAX.cond ? h("button.btn.small.ghost.ag-add", { onclick: async () => {
        let o = opts()[0];
        if (!o) { const name = (await ask(T("Name of the new switch"))); const f = name && newFlag(name); if (!f) return; o = [`flag:${f.id}:0`]; }
        const [k, rid] = o[0].split(":"); list.push({ k, id: +rid, not: false }); onChange(); draw();
      } }, "＋ ", T("Condition")) : null);
    draw();
    return box;
  };
  const actionEditor = (list, onChange) => {
    const box = h("div.ag-acts");
    const targets = k => k === "give" || k === "take" ? data.items.map(x => [x.id, "🎒 " + nm(x)]) : k === "set" || k === "clear" ? data.flags.map(x => [x.id, "🚩 " + nm(x)])
      : k === "go" ? data.rooms.map(x => [x.id, "🚪 " + nm(x, "#" + x.id)]) : k === "end" ? data.endings.map(x => [x.id, endLabel(x)]) : [];
    const draw = () => sbSet(box,
      ...list.map((a, i) => {
        const kind = h("select.ag-akind", { "aria-label": T("What happens") }, ...Object.entries(AG_ACTS()).map(([k, [ic, l]]) => h("option", { value: k, selected: k === a.k }, ic + " " + I18N.tr(l))));
        kind.onchange = () => { const k = kind.value; list[i] = k === "say" ? { k, v: "" } : { k, id: (targets(k)[0] || [null])[0] }; onChange(); draw(); };
        let arg;
        if (a.k === "say") {
          arg = h("input.ag-asay", { type: "text", maxlength: 300, value: a.v || "", lang: meta.lang, placeholder: I18N.tr(T("Text the player reads")) });
          arg.oninput = () => { a.v = arg.value; onChange(); };
        } else {
          const ts = targets(a.k);
          arg = h("select.ag-atarget", { "aria-label": T("Target") }, ...ts.map(([v, l]) => h("option", { value: v, selected: v === a.id, translate: "no" }, l)),
            !ts.some(([v]) => v === a.id) ? h("option", { value: "", selected: true }, "⚠️ ", T("choose")) : null,
            a.k === "give" || a.k === "take" ? h("option", { value: "new" }, "＋ ", T("New item …")) : a.k === "set" || a.k === "clear" ? h("option", { value: "new" }, "＋ ", T("New switch …"))
              : a.k === "end" ? h("option", { value: "new" }, "＋ ", T("New ending")) : a.k === "go" ? h("option", { value: "new" }, "＋ ", T("New room")) : null);
          arg.onchange = async () => {
            if (arg.value === "new") {
              let x = null;
              if (a.k === "give" || a.k === "take") { const n = (await ask(T("Name of the new item"))); x = n && newItem(n); }
              else if (a.k === "set" || a.k === "clear") { const n = (await ask(T("Name of the new switch"))); x = n && newFlag(n); }
              else if (a.k === "end") x = newEnding("win");
              else if (a.k === "go") x = newRoom();
              if (!x) return draw();
              a.id = x.id;
            } else a.id = +arg.value || null;
            onChange(); draw();
          };
        }
        return h("div.ag-arow", kind, arg, h("button.icon-btn.ag-x", { title: T("Remove"), "aria-label": T("Remove"), onclick: () => { list.splice(i, 1); onChange(); draw(); } }, "✕"));
      }),
      list.length < AG_MAX.actions ? h("button.btn.small.ghost.ag-add", { onclick: () => { list.push({ k: "say", v: "" }); onChange(); draw(); } }, "＋ ", T("Action")) : null);
    draw();
    return box;
  };

  // ---------- 🗺️ map: rooms as boxes, doors as arrows
  const drawMap = () => {
    const W = 140, H = 66, GX = 36, GY = 70, PAD = 20;
    const by = new Map(data.rooms.map(r => [r.id, r]));
    const depth = new Map(), order = [];
    const queue = data.start && by.has(data.start) ? [data.start] : [];
    if (queue.length) depth.set(data.start, 0);
    const outs = r => r.spots.filter(s => s.kind === "door" && s.to && by.has(s.to)).map(s => s.to);
    while (queue.length) {
      const rid = queue.shift(); order.push(rid);
      for (const t of outs(by.get(rid))) if (!depth.has(t)) { depth.set(t, depth.get(rid) + 1); queue.push(t); }
    }
    const rows = [];
    order.forEach(rid => (rows[depth.get(rid)] = rows[depth.get(rid)] || []).push(rid));
    const lost = data.rooms.filter(r => !depth.has(r.id)).map(r => r.id);
    if (lost.length) rows.push(lost);
    const cols = Math.max(1, ...rows.map(r => r.length));
    const width = PAD * 2 + cols * W + (cols - 1) * GX + 60, height = PAD * 2 + rows.length * H + (rows.length - 1) * GY + 30;
    const pos = new Map();
    rows.forEach((r, y) => { const off = (width - 60 - (r.length * W + (r.length - 1) * GX)) / 2;
      r.forEach((rid, x) => pos.set(rid, { x: off + x * (W + GX), y: PAD + y * (H + GY) })); });
    const bad = new Set((ed.issues || []).filter(i => i.room && i.level !== "warn").map(i => i.room));
    const NS = "http://www.w3.org/2000/svg";
    const S_ = (tag, attrs = {}, ...kids) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); kids.forEach(k => k != null && e.append(k)); return e; };
    if (zoom == null) zoom = Math.max(0.55, Math.min(1, ((body.clientWidth || full.clientWidth) - 24) / width));
    const svg = S_("svg", { width: width * zoom, height: height * zoom, viewBox: `0 0 ${width} ${height}`, class: "sb-svg", translate: "no" });
    svg.append(S_("defs", {}, S_("marker", { id: "agArrow", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" },
      S_("path", { d: "M0 0 L10 5 L0 10 z", class: "sb-arrowhead" }))));
    const edges = S_("g"), boxes = S_("g");
    for (const r of data.rooms) {
      const a = pos.get(r.id);
      const doors = r.spots.filter(s => s.kind === "door");
      doors.forEach((s, i) => {
        const x1 = a.x + W / 2 + (i - (doors.length - 1) / 2) * 18, y1 = a.y + H;
        const lock = s.lock && s.lock.length;
        if (s.end) {
          const e = data.endings.find(x => x.id === s.end);
          edges.append(S_("path", { d: `M${x1} ${y1} l0 20`, class: "sb-edge" + (lock ? " need" : "") }),
            S_("text", { x: x1, y: y1 + 34, class: "sb-elabel", "text-anchor": "middle" }, (e && e.kind === "lose" ? "💀" : "🏆") + (lock ? "🔒" : "")));
          return;
        }
        const b = s.to && pos.get(s.to);
        if (!b) { edges.append(S_("path", { d: `M${x1} ${y1} l0 16`, class: "sb-edge open" }), S_("text", { x: x1, y: y1 + 28, class: "sb-elabel open", "text-anchor": "middle" }, "?")); return; }
        let d;
        if (b.y > a.y) { const x2 = b.x + W / 2, y2 = b.y; d = `M${x1} ${y1} C${x1} ${y1 + GY / 2} ${x2} ${y2 - GY / 2} ${x2} ${y2 - 2}`; }
        else if (b.y < a.y) { const x2 = b.x + W, y2 = b.y + H / 2, bend = Math.max(a.x + W, b.x + W) + 30;
          d = `M${x1} ${y1} C${x1} ${y1 + 22} ${bend} ${y1 + 22} ${bend} ${(y1 + y2) / 2} S${x2 + 30} ${y2} ${x2 + 2} ${y2}`; }
        else { const x2 = b.x + (b.x > a.x ? 0 : W), y2 = b.y + H / 2; d = `M${a.x + (b.x > a.x ? W : 0)} ${a.y + H / 2} L${x2 + (b.x > a.x ? -2 : 2)} ${y2}`; }
        edges.append(S_("path", { d, class: "sb-edge" + (lock ? " need" : ""), "marker-end": "url(#agArrow)" }));
        if (lock) edges.append(S_("text", { x: x1 + 6, y: y1 + 14, class: "sb-elabel" }, "🔒"));
      });
      const g = S_("g", { class: "sb-node k-scene" + (bad.has(r.id) ? " bad" : "") + (!depth.has(r.id) ? " lost" : "") + (r.id === data.start ? " start" : ""),
        transform: `translate(${a.x} ${a.y})`, tabindex: 0, role: "button" });
      const open = () => { cur = r.id; sel = null; goTo("rooms"); };
      g.addEventListener("click", open); g.addEventListener("keydown", e => { if (e.key === "Enter") open(); });
      const n = { door: 0, object: 0, person: 0 }; r.spots.forEach(s => n[s.kind]++);
      g.append(S_("rect", { width: W, height: H, rx: 12 }),
        S_("text", { x: 10, y: 24, class: "sb-nnum" }, (r.id === data.start ? "⭐ " : "") + ((r.name || "…").length > 15 ? r.name.slice(0, 14) + "…" : r.name || "…")),
        S_("text", { x: 10, y: 50, class: "sb-ntext" }, `🚪${n.door}  📦${n.object}  🧙${n.person}`));
      if (bad.has(r.id)) g.append(S_("text", { x: W - 8, y: H - 8, class: "sb-nwarn", "text-anchor": "end" }, "⚠️"));
      boxes.append(g);
    }
    svg.append(edges, boxes);
    const z = f => { zoom = Math.max(0.4, Math.min(2, zoom * f)); drawMap(); };
    sbSet(body,
      h("div.sb-maphead", h("div.sb-legend.small", h("span", "⭐ ", T("Start room")), h("span", "→ ", T("Door")), h("span", "🔒 ", T("Locked door")),
        h("span", "🏆💀 ", T("Ending")), h("span.sb-lg-bad", "⚠️ ", T("needs work")), h("span.sb-lg-lost", T("cannot be reached"))),
        h("div.sb-zoom", h("button.icon-btn", { title: T("Zoom out"), "aria-label": T("Zoom out"), onclick: () => z(1 / 1.25) }, "−"),
          h("button.icon-btn", { title: T("Zoom in"), "aria-label": T("Zoom in"), onclick: () => z(1.25) }, "+"))),
      h("div.sb-map", svg),
      h("div.sb-addrow", h("button.btn.small", { onclick: () => { const r = newRoom(); if (r) { cur = r.id; sel = null; changed(); goTo("rooms"); } } }, "＋ ", T("Room")),
        h("span.small.muted", T("Tap a room to edit it. Arrows are doors, dashed ones are locked."))));
  };

  // ---------- 🚪 rooms: the picture with the hotspots, the hotspot sheet
  const drawRooms = () => {
    if (!room(cur)) cur = (data.rooms[0] || {}).id;
    const r = room(cur);
    const chips = h("div.ag-rchips", ...data.rooms.map(x => h("button.sb-tchip" + (x.id === cur ? ".on" : ""), { type: "button",
      onclick: () => { cur = x.id; sel = null; drawing = false; drawBody(); } }, x.id === data.start ? "⭐ " : "", C(x.name || "#" + x.id))),
      data.rooms.length < AG_MAX.rooms ? h("button.sb-tchip", { type: "button", onclick: () => { const n = newRoom(); if (n) { cur = n.id; sel = null; changed(true); } } }, "＋ ", T("Room")) : null);
    if (!r) return sbSet(body, chips);
    const name = h("input.ag-rnamein", { type: "text", maxlength: 40, value: r.name, lang: meta.lang, placeholder: I18N.tr(T("Name of the room")) });
    name.oninput = () => { r.name = name.value; changed(); };
    name.onchange = () => drawBody();
    const text = h("textarea.sb-ptext.ag-rtextin", { rows: 3, maxlength: 800, lang: meta.lang, placeholder: I18N.tr(T("What does the player see here?")) });
    text.value = r.text;
    text.oninput = () => { r.text = text.value; changed(); };
    const variants = h("details.ag-variants", { open: r.variants.length > 0 },
      h("summary", "🔀 ", T("Changes when …"), r.variants.length ? h("small", " (" + r.variants.length + ")") : null),
      h("p.small.muted", T("Another description or picture while a condition holds (e.g. after the light is switched on). The first one that holds wins.")),
      ...r.variants.map((v, i) => {
        const vt = h("textarea.sb-ptext", { rows: 2, maxlength: 800, lang: meta.lang, placeholder: I18N.tr(T("Description then")) });
        vt.value = v.text; vt.oninput = () => { v.text = vt.value; changed(); };
        return h("div.ag-variant", h("div.ag-vhead", h("b.small", sbFmt(T("Variant {0}"), i + 1)), h("span.grow"),
          h("button.btn.small.ghost", { onclick: () => bgDialog(v, true) }, "🖼️ ", v.bg ? T("Other picture") : T("Same picture")),
          h("button.icon-btn.sb-del", { title: T("Remove"), "aria-label": T("Remove"), onclick: () => { r.variants.splice(i, 1); changed(true); } }, "🗑")),
          h("div.small", h("b", T("When")), condEditor(v.if, () => changed(), T("choose a condition"))), vt);
      }),
      r.variants.length < AG_MAX.variants ? h("button.btn.small.ghost", { onclick: () => { r.variants.push({ if: [], text: "", bg: null }); changed(true); } }, "＋ ", T("Variant")) : null);
    const card = h("section.card.ag-rcard",
      h("div.ag-rhead", name,
        r.id === data.start ? h("span.sb-startchip", "⭐ ", T("Start")) : h("button.btn.small.ghost", { onclick: () => { data.start = r.id; changed(true); } }, "⭐ ", T("Start here")),
        h("button.btn.small.ghost", { onclick: () => test(r.id), title: T("Test play from this room") }, "▶"),
        h("button.icon-btn.sb-del", { title: T("Remove room"), "aria-label": T("Remove room"), onclick: async () => {
          if ((r.spots.length || r.text) && !(await confirmDialog(I18N.tr(T("Remove this room with all its hotspots?"))))) return;
          r.spots.forEach(s => purge("spot", s.id)); purge("room", r.id);
          data.rooms.splice(data.rooms.indexOf(r), 1);
          if (data.start === r.id) data.start = (data.rooms[0] || {}).id || null;
          cur = (data.rooms[0] || {}).id; sel = null; changed(true);
        } }, "🗑")),
      sceneEditor(r),
      text, variants);
    sbSet(body, chips, card, sel && r.spots.some(s => s.id === sel) ? spotSheet(r, r.spots.find(s => s.id === sel)) : h("p.small.muted.ag-tip", "👆 ", T("Tap a hotspot to change it – or draw a new one.")));
  };
  // the picture: draw a rectangle (✏️), tap to choose, drag to move, the corner to resize – in percent of the picture
  const sceneEditor = r => {
    const box = h("div.ag-escene" + (drawing ? ".drawing" : ""));
    const pct = e => { const b = box.getBoundingClientRect(); return [Math.max(0, Math.min(100, (e.clientX - b.left) / b.width * 100)), Math.max(0, Math.min(100, (e.clientY - b.top) / b.height * 100))]; };
    const r1 = v => Math.round(v * 10) / 10;
    const place = (el, s) => Object.assign(el.style, { left: s.x + "%", top: s.y + "%", width: s.w + "%", height: s.h + "%" });
    const els = r.spots.map(s => {
      const el = h("div.ag-espot.k-" + s.kind + (sel === s.id ? ".on" : ""), { title: s.name, "data-id": s.id },
        agArt(s.art), h("span.ag-elabel", (AG_KINDS()[s.kind] || [""])[0], " ", C(s.name || "…")), sel === s.id ? h("span.ag-handle", { "aria-hidden": "true" }) : null);
      place(el, s);
      el.addEventListener("pointerdown", e => {
        if (drawing || e.button > 0) return;
        e.stopPropagation();
        if (sel !== s.id) { sel = s.id; drawBody(); return; }
        e.preventDefault();
        const resize = e.target.classList.contains("ag-handle"), [x0, y0] = pct(e), start = { ...s };
        el.setPointerCapture(e.pointerId);
        let movedAny = false;
        const mv = ev => {
          const [x, y] = pct(ev), dx = x - x0, dy = y - y0;
          if (Math.abs(dx) + Math.abs(dy) > 0.5) movedAny = true;
          if (resize) { s.w = r1(Math.max(3, Math.min(100 - s.x, start.w + dx))); s.h = r1(Math.max(3, Math.min(100 - s.y, start.h + dy))); }
          else { s.x = r1(Math.max(0, Math.min(100 - s.w, start.x + dx))); s.y = r1(Math.max(0, Math.min(100 - s.h, start.y + dy))); }
          place(el, s);
        };
        const up = () => { el.removeEventListener("pointermove", mv); el.removeEventListener("pointerup", up); el.removeEventListener("pointercancel", up); if (movedAny) changed(); };
        el.addEventListener("pointermove", mv); el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
      });
      return el;
    });
    // ✏️ draw a new hotspot
    let draft = null, from = null;
    box.addEventListener("pointerdown", e => {
      if (!drawing || e.button > 0) return;
      if (r.spots.length >= AG_MAX.spots) { toast(I18N.tr(T("A room can have at most 30 hotspots")), "bad"); return; }
      e.preventDefault();
      box.setPointerCapture(e.pointerId);
      from = pct(e);
      draft = h("div.ag-espot.draft"); box.append(draft);
      place(draft, { x: from[0], y: from[1], w: 0, h: 0 });
    });
    box.addEventListener("pointermove", e => {
      if (!draft) return;
      const [x, y] = pct(e);
      place(draft, { x: Math.min(x, from[0]), y: Math.min(y, from[1]), w: Math.abs(x - from[0]), h: Math.abs(y - from[1]) });
    });
    const done = e => {
      if (!draft) return;
      const [x, y] = pct(e);
      draft.remove(); draft = null;
      let s = { x: r1(Math.min(x, from[0])), y: r1(Math.min(y, from[1])), w: r1(Math.abs(x - from[0])), h: r1(Math.abs(y - from[1])) };
      if (s.w < 3 || s.h < 3) s = { x: r1(Math.max(0, Math.min(84, from[0] - 8))), y: r1(Math.max(0, Math.min(80, from[1] - 10))), w: 16, h: 20 };   // a tap: a standard box
      const sp = { id: nextSpot(), kind: newKind, name: "", ...s, art: null, if: [], look: "", to: null, end: null, lock: [], locked: "", take: false, keep: false, item: null, talk: null };
      r.spots.push(sp); sel = sp.id; drawing = false; changed(true);
      setTimeout(() => { const n = full.querySelector(".ag-sheet input"); if (n) n.focus({ preventScroll: true }); }, 80);
    };
    box.addEventListener("pointerup", done); box.addEventListener("pointercancel", () => { if (draft) { draft.remove(); draft = null; } });
    box.addEventListener("click", e => { if (!drawing && e.target === box.firstChild && sel) { sel = null; drawBody(); } });
    const K = AG_KINDS();
    return h("div.ag-scenewrap",
      h("div.ag-drawbar",
        h("button.btn.small" + (drawing ? "" : ".ghost"), { onclick: () => { drawing = !drawing; drawBody(); } }, drawing ? ["✕ ", T("Cancel")] : ["✏️ ", T("Draw hotspot")]),
        drawing ? h("div.sb-segs", ...Object.entries(K).map(([k, [ic, l]]) => h("button.sb-seg" + (newKind === k ? ".on" : ""), { title: l, "aria-label": l,
          onclick: () => { newKind = k; drawBody(); } }, ic, h("span.ag-hide-s", " ", l)))) : null,
        h("button.btn.small.ghost", { onclick: () => bgDialog(r) }, "🖼️ ", T("Picture"))),
      drawing ? h("p.small.ag-drawhint", "👉 ", T("Drag a rectangle over the thing on the picture (or just tap).")) : null,
      (box.append(agBg(r.bg), ...els), box));
  };
  // the property sheet of a hotspot
  const spotSheet = (r, s) => {
    const K = AG_KINDS();
    const name = h("input", { type: "text", maxlength: 40, value: s.name, lang: meta.lang, placeholder: I18N.tr(T("e.g. Old chest")) });
    name.oninput = () => { s.name = name.value; changed(); const l = full.querySelector(`.ag-espot[data-id="${s.id}"] .ag-elabel span`); if (l) l.textContent = s.name || "…"; };
    const look = h("textarea.sb-ptext", { rows: 2, maxlength: 400, lang: meta.lang, placeholder: I18N.tr(T("What the player reads when looking at it")) });
    look.value = s.look; look.oninput = () => { s.look = look.value; changed(); };
    const kinds = h("div.sb-kinds", ...Object.entries(K).map(([k, [ic, l]]) => h("button.sb-kind" + (s.kind === k ? ".on" : ""), { title: l, "aria-label": l,
      onclick: () => { if (s.kind !== k) { s.kind = k; changed(true); } } }, ic, " ", l)));
    let extra;
    if (s.kind === "door") {
      const to = h("select", { "aria-label": T("Leads to") },
        h("option", { value: "" }, "→ ", T("choose")),
        h("optgroup", { label: I18N.tr(T("Rooms")) }, ...data.rooms.filter(x => x.id !== r.id).map(x => h("option", { value: "r" + x.id, selected: s.to === x.id && !s.end, translate: "no" }, "🚪 " + nm(x, "#" + x.id)))),
        h("optgroup", { label: I18N.tr(T("Endings")) }, ...data.endings.map(e => h("option", { value: "e" + e.id, selected: s.end === e.id, translate: "no" }, endLabel(e)))),
        h("option", { value: "new:room" }, "＋ ", T("New room")), h("option", { value: "new:win" }, "＋ 🏆 ", T("New winning ending")), h("option", { value: "new:lose" }, "＋ 💀 ", T("New losing ending")));
      to.onchange = () => {
        const v = to.value;
        s.to = null; s.end = null;
        if (v === "new:room") { const n = newRoom(); if (n) { s.to = n.id; n.spots.push({ id: nextSpot(), kind: "door", name: r.name ? r.name : "", x: 2, y: 30, w: 16, h: 50,
          art: { k: "asset", v: "door" }, if: [], look: "", to: r.id, end: null, lock: [], locked: "", take: false, keep: false, item: null, talk: null }); toast(I18N.tr(T("New room with a door back")), "good"); } }
        else if (v === "new:win" || v === "new:lose") { const e = newEnding(v.slice(4)); if (e) { s.end = e.id; toast(I18N.tr(T("Write the ending text under 🎒 Things")), "good"); } }
        else if (v[0] === "r") s.to = +v.slice(1);
        else if (v[0] === "e") s.end = +v.slice(1);
        changed(true);
      };
      const locked = h("input", { type: "text", maxlength: 400, value: s.locked, lang: meta.lang, placeholder: I18N.tr(T("e.g. The door is locked. Where is the key?")) });
      locked.oninput = () => { s.locked = locked.value; changed(); };
      extra = [h("label.field", h("b", T("Leads to")), h("div.row", to, s.to ? h("button.btn.small.ghost", { onclick: () => { cur = s.to; sel = null; drawBody(); } }, "↘") : null)),
        h("div.field", h("b", "🔒 ", T("Opens only when")), condEditor(s.lock, () => changed(true), T("always open"))),
        s.lock.length ? h("label.field", h("span", T("Text when it is locked")), locked) : null];
    } else if (s.kind === "object") {
      const take = h("input", { type: "checkbox", checked: s.take });
      take.onchange = () => {
        s.take = take.checked;
        if (s.take && !s.item) { const it = data.items.find(x => x.name === s.name) || (s.name ? newItem(s.name) : null); if (it) { s.item = it.id; if (!it.icon && s.art) it.icon = s.art; } }
        changed(true);
      };
      const item = h("select", { "aria-label": T("Item") }, h("option", { value: "" }, "🎒 ", T("choose")),
        ...data.items.map(x => h("option", { value: x.id, selected: s.item === x.id, translate: "no" }, "🎒 " + nm(x))), h("option", { value: "new" }, "＋ ", T("New item …")));
      item.onchange = async () => { if (item.value === "new") { const n = (await ask(T("Name of the new item"), s.name)); const it = n && newItem(n); s.item = it ? it.id : s.item; if (it && s.art) it.icon = s.art; }
        else s.item = +item.value || null; changed(true); };
      const keep = h("input", { type: "checkbox", checked: !!s.keep });
      keep.onchange = () => { s.keep = keep.checked; changed(); };
      extra = [h("label.check", take, " ✋ ", T("Can be taken (goes into the backpack)")), s.take ? h("label.field", h("b", T("Becomes the item")), item) : null,
        s.take ? h("label.check", keep, " 📦 ", T("Stays in the room – only the item goes into the backpack (e.g. a chest with a key)")) : null];
    } else {
      const line = h("select", { "aria-label": T("Dialogue") }, h("option", { value: "" }, "💬 ", T("choose")),
        ...data.lines.map(x => h("option", { value: x.id, selected: s.talk === x.id, translate: "no" }, lineLabel(x))), h("option", { value: "new" }, "＋ ", T("New dialogue")));
      line.onchange = () => { if (line.value === "new") { const l = newLine(); if (l) s.talk = l.id; } else s.talk = +line.value || null; changed(true); };
      extra = [h("label.field", h("b", T("Talks with the line")), h("div.row", line,
        s.talk ? h("button.btn.small.ghost", { onclick: () => goTo("talk", () => flash("#agl-" + s.talk)) }, "💬 ", T("Edit")) : null))];
    }
    const rules = data.rules.filter(x => x.kind === "use" && x.spot === s.id);
    return h("section.card.ag-sheet",
      h("div.ag-shead", kinds, h("span.grow"),
        h("button.icon-btn.sb-del", { title: T("Remove hotspot"), "aria-label": T("Remove hotspot"), onclick: () => {
          purge("spot", s.id); r.spots.splice(r.spots.indexOf(s), 1); sel = null; changed(true); } }, "🗑")),
      h("div.ag-sgrid",
        h("button.ag-artbtn", { title: T("Picture"), onclick: () => artDialog(s, "art") }, s.art ? agArt(s.art) : h("span.sb-nopic", "👻", h("span.small", T("invisible")))),
        h("div.ag-sfields", h("label.field", h("b", T("Name")), name), h("label.field", h("span", "👁️ ", T("Look at")), look))),
      ...extra,
      h("div.field", h("b", "👁️ ", T("Visible only when")), condEditor(s.if, () => changed(true), T("always visible"))),
      h("div.field", h("b", "🔧 ", T("Use rules")),
        rules.length ? h("ul.ag-rlist", ...rules.map(x => h("li", h("button.link", { onclick: () => goTo("rules", () => flash("#agr-" + x.id)) }, ruleText(x))))) : null,
        h("button.btn.small.ghost", { onclick: () => { if (data.rules.length >= AG_MAX.rules) return; const x = { id: nextId(data.rules), kind: "use", item: null, spot: s.id, if: [], do: [{ k: "say", v: "" }] };
          data.rules.push(x); changed(); goTo("rules", () => flash("#agr-" + x.id)); } }, "＋ ", T("What happens when it is used"))));
  };
  const ruleText = x => x.kind === "combine"
    ? "🧪 " + nm(data.items.find(i => i.id === x.item)) + " + " + nm(data.items.find(i => i.id === x.item2))
    : "🔧 " + (x.item ? nm(data.items.find(i => i.id === x.item)) : I18N.tr(T("just use it"))) + " → " + nm((spots().find(([s]) => s.id === x.spot) || [])[0]);

  // ---------- 🎒 things: items, switches, endings
  const drawThings = () => {
    const itemRow = it => {
      const n = h("input", { type: "text", maxlength: 40, value: it.name, lang: meta.lang, placeholder: I18N.tr(T("e.g. Old key")) });
      n.oninput = () => { it.name = n.value; changed(); };
      return h("div.ag-trow", h("button.ag-ticon", { title: T("Picture"), onclick: () => artDialog(it, "icon") }, it.icon ? agArt(it.icon) : h("span.ag-emo", "🎒")), n,
        h("button.icon-btn.sb-del", { title: T("Remove"), "aria-label": T("Remove"), onclick: async () => { if (!(await confirmDialog(I18N.tr(T("Remove this item everywhere in the game?"))))) return;
          purge("item", it.id); data.items.splice(data.items.indexOf(it), 1); changed(true); } }, "🗑"));
    };
    const flagRow = f => {
      const n = h("input", { type: "text", maxlength: 40, value: f.name, lang: meta.lang, placeholder: I18N.tr(T("e.g. Dragon sleeps")) });
      n.oninput = () => { f.name = n.value; changed(); };
      return h("div.ag-trow", h("span.ag-ticon", "🚩"), n, h("button.icon-btn.sb-del", { title: T("Remove"), "aria-label": T("Remove"), onclick: async () => {
        if (!(await confirmDialog(I18N.tr(T("Remove this switch everywhere in the game?"))))) return; purge("flag", f.id); data.flags.splice(data.flags.indexOf(f), 1); changed(true); } }, "🗑"));
    };
    const endRow = e => {
      const t = h("textarea.sb-ptext", { rows: 2, maxlength: 800, lang: meta.lang, placeholder: I18N.tr(e.kind === "win" ? T("How does the player win?") : T("What goes wrong?")) });
      t.value = e.text; t.oninput = () => { e.text = t.value; changed(); };
      return h("div.ag-endrow.k-" + e.kind, h("div.ag-vhead", h("div.sb-kinds", ...[["win", "🏆", T("Win")], ["lose", "💀", T("Lose")]].map(([k, ic, l]) =>
        h("button.sb-kind" + (e.kind === k ? ".on" : ""), { onclick: () => { e.kind = k; changed(true); } }, ic, " ", l))), h("span.grow"),
        h("button.icon-btn.sb-del", { title: T("Remove"), "aria-label": T("Remove"), onclick: () => { purge("end", e.id); data.endings.splice(data.endings.indexOf(e), 1); changed(true); } }, "🗑")), t);
    };
    sbSet(body, h("div.ag-things",
      h("section.card.ag-tcard", h("h3", "🎒 ", T("Items"), h("small", " ", data.items.length + "/" + AG_MAX.items)),
        h("p.small.muted", T("Things the player carries in the backpack. Objects become items when they are taken; rules and answers give them too.")),
        ...data.items.map(itemRow),
        h("button.btn.small.ghost", { onclick: () => { if (newItem("")) changed(true); } }, "＋ ", T("Item"))),
      h("section.card.ag-tcard", h("h3", "🚩 ", T("Switches"), h("small", " ", data.flags.length + "/" + AG_MAX.flags)),
        h("p.small.muted", T("Things the game remembers, e.g. «Light is on» or «Dragon sleeps». Rules and answers switch them on and off; conditions ask for them.")),
        ...data.flags.map(flagRow),
        h("button.btn.small.ghost", { onclick: () => { if (newFlag("")) changed(true); } }, "＋ ", T("Switch"))),
      h("section.card.ag-tcard", h("h3", "🏁 ", T("Endings")),
        h("p.small.muted", T("A door or an action ends the game. Players collect the endings – at least one must be a win.")),
        ...data.endings.map(endRow),
        h("div.row", h("button.btn.small.ghost", { onclick: () => { if (newEnding("win")) changed(true); } }, "＋ 🏆 ", T("Win")),
          h("button.btn.small.ghost", { onclick: () => { if (newEnding("lose")) changed(true); } }, "＋ 💀 ", T("Lose"))))));
  };

  // ---------- 💬 dialogues
  const drawTalk = () => {
    const who = l => spots().filter(([s]) => s.kind === "person" && s.talk === l.id).map(([s]) => s.name || "…");
    const lineCard = (l, n) => {
      const t = h("textarea.sb-ptext", { rows: 2, maxlength: 400, lang: meta.lang, placeholder: I18N.tr(T("What does the character say?")) });
      t.value = l.text; t.oninput = () => { l.text = t.value; changed(); };
      const ans = l.answers.map((a, i) => {
        const at = h("input", { type: "text", maxlength: 120, value: a.t, lang: meta.lang, placeholder: sbFmt(T("Answer {0}"), i + 1) });
        at.oninput = () => { a.t = at.value; changed(); };
        const next = h("select", { "aria-label": T("Then") }, h("option", { value: "" }, "👋 ", T("end of the talk")),
          ...data.lines.map(x => h("option", { value: x.id, selected: a.next === x.id, translate: "no" }, "→ " + lineLabel(x))),
          h("option", { value: "new" }, "＋ ", T("New line")));
        next.onchange = () => { if (next.value === "new") { const nl = newLine(); if (nl) a.next = nl.id; } else a.next = +next.value || null; changed(true); };
        return h("div.ag-answer-ed",
          h("div.ag-arowtop", h("span.ag-anum", String(i + 1)), at,
            h("button.icon-btn.ag-x", { title: T("Remove"), "aria-label": T("Remove"), onclick: () => { l.answers.splice(i, 1); changed(true); } }, "✕")),
          h("div.ag-aopts", h("label.field", h("span.small", T("Then")), next),
            h("details.ag-amore", { open: a.if.length > 0 || a.do.length > 0 }, h("summary.small", "⚙️ ", T("Condition and actions"), a.if.length || a.do.length ? " •" : ""),
              h("div.small", h("b", T("Only when")), condEditor(a.if, () => changed(), T("always"))),
              h("div.small", h("b", T("What happens")), actionEditor(a.do, () => changed())))));
      });
      return h("section.card.ag-lcard", { id: "agl-" + l.id },
        h("div.ag-vhead", h("span.sb-pnum", String(n)), who(l).length ? h("span.sb-startchip", "🧙 ", C(who(l).join(", "))) : null, h("span.grow"),
          h("button.icon-btn.sb-del", { title: T("Remove"), "aria-label": T("Remove"), onclick: () => { purge("line", l.id); data.lines.splice(data.lines.indexOf(l), 1); changed(true); } }, "🗑")),
        t, h("b.small", T("Answers of the player")), ...ans,
        l.answers.length < AG_MAX.answers ? h("button.btn.small.ghost", { onclick: () => { l.answers.push({ t: "", if: [], do: [], next: null }); changed(true); } }, "＋ ", T("Answer")) : null);
    };
    sbSet(body, h("p.small.muted", T("A character starts with one line; every answer of the player can need a condition, do things (give an item, switch something on …) and lead to the next line. 👋 Leave always works.")),
      h("div.sb-cards", ...data.lines.map((l, i) => lineCard(l, i + 1))),
      h("div.sb-addrow", h("button.btn.small", { onclick: () => { const l = newLine(); if (l) { changed(true); flash("#agl-" + l.id); } } }, "＋ ", T("Dialogue line"))));
  };

  // ---------- ⚙️ rules: use X on Y, combine A + B
  const drawRules = () => {
    const itemSel = (val, onPick, none = null) => {
      const s = h("select", { "aria-label": T("Item") }, none ? h("option", { value: "", selected: !val }, none) : h("option", { value: "", selected: !val }, "🎒 ", T("choose")),
        ...data.items.map(x => h("option", { value: x.id, selected: val === x.id, translate: "no" }, "🎒 " + nm(x))), h("option", { value: "new" }, "＋ ", T("New item …")));
      s.onchange = async () => { if (s.value === "new") { const n = (await ask(T("Name of the new item"))); const it = n && newItem(n); onPick(it ? it.id : val); } else onPick(+s.value || null); changed(true); };
      return s;
    };
    const card = x => {
      const parts = x.kind === "use"
        ? [h("label.field", h("span.small", "🔧 ", T("Use")), itemSel(x.item, v => { x.item = v; }, "✋ " + I18N.tr(T("just use it (no item)")))),
          h("label.field", h("span.small", T("on")), (() => {
            const s = h("select", { "aria-label": T("Hotspot") }, h("option", { value: "" }, T("choose a hotspot")),
              ...data.rooms.map(r => h("optgroup", { label: r.name || "#" + r.id }, ...r.spots.map(sp => h("option", { value: sp.id, selected: x.spot === sp.id, translate: "no" },
                (AG_KINDS()[sp.kind] || [""])[0] + " " + (sp.name || "…"))))));
            s.onchange = () => { x.spot = +s.value || null; changed(true); };
            return s;
          })())]
        : [h("label.field", h("span.small", "🧪 ", T("Combine")), itemSel(x.item, v => { x.item = v; })), h("label.field", h("span.small", "+"), itemSel(x.item2, v => { x.item2 = v; }))];
      return h("section.card.ag-rulecard", { id: "agr-" + x.id },
        h("div.ag-vhead", h("div.sb-kinds", ...[["use", "🔧", T("Use")], ["combine", "🧪", T("Combine")]].map(([k, ic, l]) => h("button.sb-kind" + (x.kind === k ? ".on" : ""),
          { onclick: () => { if (x.kind !== k) { x.kind = k; if (k === "use") { x.spot = x.spot || null; delete x.item2; } else { x.item2 = x.item2 || null; delete x.spot; } changed(true); } } }, ic, " ", l))),
          h("span.grow"), h("button.icon-btn.sb-del", { title: T("Remove"), "aria-label": T("Remove"), onclick: () => { data.rules.splice(data.rules.indexOf(x), 1); changed(true); } }, "🗑")),
        h("div.ag-rparts", ...parts),
        h("div.small", h("b", T("Only when")), condEditor(x.if, () => changed(), T("always"))),
        h("div.small", h("b", T("What happens")), actionEditor(x.do, () => changed())));
    };
    const add = kind => { if (data.rules.length >= AG_MAX.rules) return toast(I18N.tr(T("A game can have at most 200 rules")), "bad");
      const x = { id: nextId(data.rules), kind, item: null, if: [], do: [{ k: "say", v: "" }], ...(kind === "use" ? { spot: null } : { item2: null }) };
      data.rules.push(x); changed(true); flash("#agr-" + x.id); };
    sbSet(body, h("p.small.muted", T("Use rules: what happens when the player uses an item on a hotspot («key → chest») or just uses it («pull the lever»). Combine rules: two items become something new («stick + rope = fishing rod»). The first rule whose condition holds wins. A key on a locked door needs no rule.")),
      h("div.sb-cards", ...data.rules.map(card)),
      h("div.sb-addrow", h("button.btn.small", { onclick: () => add("use") }, "＋ 🔧 ", T("Use rule")), h("button.btn.small", { onclick: () => add("combine") }, "＋ 🧪 ", T("Combine rule"))));
  };
  const drawBody = () => { ({ map: drawMap, rooms: drawRooms, things: drawThings, talk: drawTalk, rules: drawRules }[mode] || drawRooms)(); };

  // ---------- pictures: a room (library, own drawing, photo, SVG code), a hotspot / an item (asset, emoji, own drawing) – svgpaint.js draws
  const bgDialog = (target, variant = false) => {
    const set = bg => { target.bg = bg; m.close(); changed(true); };
    let tab = "lib";
    const box = h("div.pb-pictab");
    const file = h("input", { type: "file", accept: "image/*", hidden: true });
    file.onchange = async () => { const f = file.files[0]; if (!f) return;
      try { const blob = await sbShrink(f); const r = await sbUpload(blob, "photo.jpg"); set({ k: "img", v: r.name, src: "photo" }); } catch (e) { toast(e.message, "bad"); } };
    const code = h("textarea.sb-imptext.pb-svgcode", { rows: 7, spellcheck: false, placeholder: "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 300'>…</svg>" });
    if (target.bg && target.bg.k === "svg") code.value = target.bg.v;
    const tile = (k, n) => h("button.sb-bgtile" + (target.bg && target.bg.k === "lib" && target.bg.v === k ? ".on" : ""), { type: "button", onclick: () => set({ k: "lib", v: k }) },
      h("span.sb-bgimg", { style: { backgroundImage: `url(${agBgUrl(k)})` } }), h("span.small", n));
    const drawTab = () => {
      for (const b of tabs.querySelectorAll(".sb-seg")) b.classList.toggle("on", b.dataset.k === tab);
      if (tab === "lib") sbSet(box, h("div.sb-bggrid", ...Object.entries(AG_ROOMS()).map(([k, n]) => tile(k, n)), ...Object.entries(SB_BGS()).map(([k, n]) => tile(k, n))));
      else if (tab === "own") sbSet(box, h("div.row.wrap.pb-ownbtns",
        h("button.btn", { onclick: async () => {
          m.close();
          const svg = await svgPaint({ kind: "bg", svg: target.bg && target.bg.k === "svg" ? target.bg.v : null });
          if (svg) { target.bg = { k: "svg", v: svg }; changed(true); }
        } }, target.bg && target.bg.k === "svg" ? ["✏️ ", T("Change drawing")] : ["🎨 ", T("Draw a picture")]),
        h("button.btn.ghost", { onclick: () => file.click() }, "📷 ", T("Photo")), file));
      else sbSet(box, h("p.small.muted", T("Paste an SVG drawing (e.g. made by an AI): simple shapes with a viewBox, max. 60 KB. Scripts, links and external files are removed.")),
        code, h("button.btn", { onclick: async () => {
          try { const r = await api("stories/svg", { method: "POST", body: { svg: code.value } }); set({ k: "svg", v: r.svg }); } catch (e) { toast(e.message, "bad"); }
        } }, "✓ ", T("Use picture")));
    };
    const tabs = h("div.sb-segs.pb-tabs", ...[["lib", "🏞️", T("Pictures")], ["own", "🎨", T("Own picture")], ["svg", "</>", T("SVG code")]]
      .map(([k, ic, n]) => h("button.sb-seg", { type: "button", "data-k": k, title: n, "aria-label": n, onclick: () => { tab = k; drawTab(); } }, h("span", { translate: "no" }, ic), h("span.sb-hide-s", " ", n))));
    const m = modal(h("div.form.pb-picdlg", h("h2", "🖼️ ", variant ? T("Picture of the variant") : T("Picture of the room")), tabs, box,
      h("div.row.wrap", target.bg || variant ? h("button.btn.ghost", { onclick: () => set(null) }, variant ? ["↩ ", T("Same picture")] : ["🗑 ", T("No picture")]) : null,
        h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))), { wide: true });
    drawTab();
  };
  const artDialog = (target, key) => {
    const set = p => { target[key] = p; m.close(); changed(true); };
    let tab = "assets";
    const box = h("div.pb-pictab");
    const own = h("input.sb-ownemo", { type: "text", maxlength: 8, placeholder: "🙂", "aria-label": T("Own emoji") });
    const drawTab = () => {
      for (const b of tabs.querySelectorAll(".sb-seg")) b.classList.toggle("on", b.dataset.k === tab);
      if (tab === "assets") sbSet(box, h("div.ag-assetgrid", ...Object.entries(AG_ASSETS()).map(([k, n]) => h("button.ag-asset" + (target[key] && target[key].v === k ? ".on" : ""),
        { type: "button", title: n, onclick: () => set({ k: "asset", v: k }) }, h("img", { src: agAssetUrl(k), alt: "", draggable: false }), h("span.small", n)))));
      else if (tab === "emoji") sbSet(box, h("div.sb-picgrid", ...SB_PICS.map(e => h("button.sb-pe", { type: "button", translate: "no", onclick: () => set({ k: "emoji", v: e }) }, e)),
        own, h("button.btn.small", { onclick: () => own.value.trim() && set({ k: "emoji", v: own.value.trim() }) }, "✓")));
      else sbSet(box, h("div.row.wrap.pb-ownbtns", h("button.btn", { onclick: async () => {
        m.close();
        const svg = await svgPaint({ kind: "art", svg: target[key] && target[key].k === "svg" ? target[key].v : null });
        if (svg) { target[key] = { k: "svg", v: svg }; changed(true); }
      } }, target[key] && target[key].k === "svg" ? ["✏️ ", T("Change drawing")] : ["🎨 ", T("Draw a thing")]),
        h("span.small.muted", T("The drawing has a see-through background, so it stands in the room."))));
    };
    const tabs = h("div.sb-segs.pb-tabs", ...[["assets", "🧸", T("Things")], ["emoji", "😀", T("Emoji")], ["own", "🎨", T("Own picture")]]
      .map(([k, ic, n]) => h("button.sb-seg", { type: "button", "data-k": k, title: n, "aria-label": n, onclick: () => { tab = k; drawTab(); } }, h("span", { translate: "no" }, ic), h("span.sb-hide-s", " ", n))));
    const m = modal(h("div.form.pb-picdlg", h("h2", "🖼️ ", T("Picture")), tabs, box,
      h("div.row.wrap", target[key] ? h("button.btn.ghost", { onclick: () => set(null) }, "👻 ", key === "art" ? T("Invisible (only the room picture)") : T("No picture")) : null,
        h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))), { wide: true });
    drawTab();
  };

  // ---------- title, colour, language, export, remove
  const metaDialog = () => {
    let emoji = meta.emoji, color = meta.color;
    const title = h("input", { type: "text", maxlength: 80, value: meta.title });
    const lang = h("select", ...I18N.LANGS.filter(([k]) => k !== "auto").map(([k, nm_]) => h("option", { value: k, translate: "no", selected: k === meta.lang }, nm_)));
    const ownE = h("input.sb-ownemo", { type: "text", maxlength: 8, placeholder: "🙂", "aria-label": T("Own emoji") });
    const pick = h("div.sb-emojis"), cols = h("div.sb-colors");
    const drawPick = () => {
      sbSet(pick, ...["🗝️", "🧙", "📦", "🚀", "👻", "🐉", "🏰", "🤖", "🏴‍☠️", "👽", "🔦", "🕵️"].map(e => h("button.sb-pe" + (e === emoji ? ".on" : ""), { type: "button", translate: "no", onclick: () => { emoji = e; ownE.value = ""; drawPick(); } }, e)), ownE);
      sbSet(cols, ...SB_COVERS.map((g, i) => h("button.sb-col" + (i === color ? ".on" : ""), { type: "button", "aria-label": String(i + 1), style: { background: g }, onclick: () => { color = i; drawPick(); } })));
    };
    ownE.oninput = () => { if (ownE.value.trim()) emoji = ownE.value.trim(); };
    drawPick();
    const runA = async (path, method, msg, after) => { try { await api(path, { method }); toast(msg, "good"); m.close(); after(); } catch (e) { toast(e.message, "bad"); } };
    const m = modal(h("div.form", h("h2", "⚙️ ", T("Game settings")),
      h("label.field", T("Title"), title), h("div.field", h("b", T("Shelf icon and colour")), pick, cols),
      h("label.field", T("Language of the game"), lang),
      h("div.row", h("button.btn", { onclick: () => {
        if (!title.value.trim()) return title.focus();
        Object.assign(meta, { title: title.value.trim(), emoji, color, lang: lang.value }); m.close(); drawHead(); changed(true);
      } }, "💾 ", T("Save")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel"))),
      h("div.row.wrap", h("button.btn.small.ghost", { onclick: async () => { await save(); downloadApi(`stories/${id}/export`, `family-quest-game-${id}.json`); } }, "⬇️ ", T("Export as a file")),
        h("span.small.muted", T("For a backup, another family or an AI – own drawings go along, photos stay out."))),
      h("div.sb-danger.row.wrap",
        ed.live || ed.pending ? h("button.btn.small.ghost", { onclick: async () => (await confirmDialog(I18N.tr(T("Take the game off the shelf? It stays here as a draft.")))) &&
          runA(`stories/${id}/unpublish`, "POST", T("The game is a draft again"), async () => { ed = await api("stories/" + id); drawHead(); }) }, "📥 ", T("Unpublish")) : null,
        h("button.btn.small.bad", { onclick: async () => (await confirmDialog(I18N.tr(T("Remove this game for good? This cannot be undone.")))) &&
          runA(`stories/${id}`, "DELETE", T("Removed"), () => { closed = true; dirty = false; clearTimeout(timer); finish(); }) }, "🗑 ", T("Remove game")))), { wide: true });
  };

  document.body.append(full);
  document.body.classList.add("quiz-open");
  setState("saved");
  drawHead(); drawChecker(); drawBody();
}
