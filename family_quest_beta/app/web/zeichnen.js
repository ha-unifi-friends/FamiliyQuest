// «Zeichnen & Raten» – live drawing and guessing for the family: everybody on their own device, guests via QR code
// (familyquest/zeichnen.py). zeichnenLive(box, me, back) runs the family table, zeichnenStartDialog(onStarted) sets the
// rules. The drawer draws on a square canvas (pointer events: touch and mouse); the strokes go to the server in small
// batches (normalised 0–1 coordinates), the others poll them with a cursor and draw only what is new.
"use strict";

const ZR_ICON = "🎨";
const zrName = () => I18N.tr(T("Draw & Guess"));
const zrCoins = list => list.join(" / ") + " 🪙";
// the category titles in the language of the app (the server sends the words and the mask in it too – familyquest/gamewords.py)
const ZR_CATS = { tiere: T("Animals"), berufe: T("Jobs"), essen: T("Food & fruit"), gegenstaende: T("Things at home"), sport: T("Sports"), gemischt: T("Mixed") };
const zrCat = c => c ? (ZR_CATS[c.key] ? I18N.tr(ZR_CATS[c.key]) : c.title) : "";
const ZR_PALETTE = ["#000000", "#7a7a7a", "#e03131", "#f76707", "#fcc419", "#2f9e44", "#1c7ed6", "#7048e8", "#8b5a2b", "#f06595"];
const ZR_WIDTH = [0.008, 0.018, 0.04];          // line width per size, as a part of the canvas width (eraser: twice)
const ZR_SEND_MS = 120;                         // a batch of strokes this often while drawing
const ZR_POLL_MS = 700;

function zeichnenRulesView(rules, rewards) {
  const items = [T("One player draws, the others guess – everybody on their own device. Everybody draws in turn."),
    T("The drawer chooses one of 3 words (10 seconds, then one is taken at random) and draws it – no letters or numbers!"),
    T("The others see the drawing live and type their guesses. Wrong guesses are shown to everybody, a right one is not."),
    rules && rules.hints ? T("Hints: some letters of the word appear at half and three quarters of the time.") : null,
    T("Capitals, accents, umlauts (ä = ae) and der / die / das do not matter; with longer words one typo is fine. «Close!» – only you see it."),
    T("Everybody sees the word in their own language: guess in yours or in the drawer's – both count."),
    T("Points: the faster you guess, the more you get (up to 100). The drawer gets 10 points for everybody who guessed it."),
    rewards ? I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", zrCoins(rewards)) : null,
    T("Coins only at a table with at least two people of the family – not for guests.")].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

async function zeichnenStartDialog(onStarted) {
  let r = {};
  try { r = await api("community/zeichnen/rules"); } catch {}
  const cats = r.categories || Object.keys(ZR_CATS).map(k => ({ key: k, emoji: "🎨" }));
  let cat = cats.some(c => c.key === r.category) ? r.category : "gemischt";
  const grid = h("div.wb-cats");
  const drawCats = () => grid.replaceChildren(...cats.map(c => h("button.wb-cat" + (c.key === cat ? ".on" : ""),
    { type: "button", "aria-pressed": String(c.key === cat), onclick: () => { cat = c.key; drawCats(); } },
    h("span.wb-cat-ic", c.emoji), h("span", zrCat(c)))));
  drawCats();
  const seg = (list, cur, label, set) => {
    const box = h("div.seg");
    const draw = () => box.replaceChildren(...list.map(n => h("button" + (n === cur ? ".on" : ""), { type: "button", onclick: () => { cur = n; set(n); draw(); } }, label(n))));
    draw();
    return box;
  };
  let rounds = r.rounds || 2, time = r.time || 80;
  const hints = h("input", { type: "checkbox", checked: r.hints !== false });
  const rw = r.rewards || [0, 0, 0];
  const coins = rw.some(x => x > 0) ? h("p.small.pj-coins", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", zrCoins(rw)), h("br"),
    h("span.muted", T("Coins only at a table with at least two people of the family – not for guests."))) : null;
  const m = modal(h("div.form", h("h2", ZR_ICON, " ", zrName()),
    h("p.small.muted", T("One draws, the others guess – live on every device. 2 to 8 players.")),
    h("div.field", h("b", T("Words")), grid),
    h("div.grid2", h("div.field", h("b", T("Everybody draws")), seg([1, 2, 3], rounds, n => n + "×", n => { rounds = n; })),
      h("div.field", h("b", T("Time to draw")), seg([60, 80, 120], time, n => n + " s", n => { time = n; }))),
    h("div.cards-rules", h("label.check", hints, T("Hints: show some letters as time runs out"))),
    coins,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      try { await api("community/zeichnen/start", { method: "POST", body: { category: cat, rounds, time, hints: hints.checked } }); m.close(); onStarted(); }
      catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
}

// ---------------------------------------------------------------- the canvas: keeps the events, draws only what is new
function zrPainter(canvas) {
  const ctx = canvas.getContext("2d");
  const P = { events: [], turn: null, painted: { n: 0, pl: 0 } };
  const W = () => canvas.width;
  function style(e) {
    ctx.strokeStyle = e.e ? "#ffffff" : (e.c || "#000");
    ctx.lineWidth = Math.max(1, (ZR_WIDTH[(e.w || 2) - 1] || ZR_WIDTH[1]) * W() * (e.e ? 2 : 1));
    ctx.lineCap = "round"; ctx.lineJoin = "round";
  }
  function seg(e, from) {                         // the points of a stroke from the number index `from` on
    const p = e.p || [], w = W();
    if (p.length < 2 || from >= p.length) return;
    style(e);
    const i = Math.max(0, from - 2);
    ctx.beginPath();
    ctx.moveTo(p[i] * w, p[i + 1] * w);
    if (p.length === 2) ctx.lineTo(p[0] * w + 0.01, p[1] * w);
    for (let j = i + 2; j < p.length; j += 2) ctx.lineTo(p[j] * w, p[j + 1] * w);
    ctx.stroke();
  }
  function visible() {                            // undo removes the last stroke, clear all
    let list = [];
    for (const e of P.events) { if (e.u) list.pop(); else if (e.x) list = []; else if (e.p) list.push(e); }
    return list;
  }
  function mark() { const last = P.events[P.events.length - 1]; P.painted = { n: P.events.length, pl: last && last.p ? last.p.length : 0 }; }
  P.redraw = () => {
    ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, W(), W());
    for (const e of visible()) seg(e, 0);
    mark();
  };
  P.resize = () => {
    const css = canvas.clientWidth || canvas.parentNode && canvas.parentNode.clientWidth || 300;
    const px = Math.round(css * Math.min(2, window.devicePixelRatio || 1));
    if (canvas.width !== px) { canvas.width = px; canvas.height = px; }
    P.redraw();
  };
  P.reset = (events, turn) => { P.events = (events || []).map(e => e.p ? { ...e, p: e.p.slice() } : { ...e }); if (turn !== undefined) P.turn = turn; P.redraw(); };
  // the drawer: a new stroke, more points, undo, clear
  P.start = e => { P.events.push(e); seg(e, 0); mark(); };
  P.more = pts => { const e = P.events[P.events.length - 1]; if (!e || !e.p) return; const from = e.p.length; e.p.push(...pts); seg(e, from); mark(); };
  P.op = e => { P.events.push(e); P.redraw(); };
  P.canUndo = () => visible().length > 0;
  // the others: what the server sent since the cursor
  P.cursor = () => ({ n: P.events.length, pl: (P.events[P.events.length - 1] || {}).p ? P.events[P.events.length - 1].p.length : 0 });
  P.merge = s => {
    if (!s) return;
    if (s.turn !== P.turn || (!s.cont && s.from === 0) || s.from > P.events.length) return P.reset(s.ev, s.turn);
    const ev = s.ev.slice();
    let full = false;
    if (s.cont && ev.length) {
      const first = ev.shift(), last = P.events[s.from];
      if (!last || !last.p) return P.reset([], s.turn);       // the cursor did not fit – the next poll brings everything
      const from = last.p.length;
      last.p.push(...first.p);
      if (!full) seg(last, from);
    }
    for (const e of ev) {
      P.events.push(e.p ? { ...e, p: e.p.slice() } : { ...e });
      if (e.u || e.x) full = true; else if (!full) seg(e, 0);
    }
    if (full) P.redraw(); else mark();
  };
  return P;
}

function zeichnenLive(box, me, back) {
  let st = null, timer = null, tick = null, sender = null, alive = true, lastSig = "", cheered = false, busy = false;
  let V = null;                       // the view of the current turn (canvas, chat, input) – kept while the turn runs
  let deadlineAt = null, lastFound = new Set(), lastPhase = null, needStrokes = true, fullWarned = false;
  let tool = { c: ZR_PALETTE[0], w: 2, e: false };
  let outq = [], cur = null, sending = false;
  const myId = String(me.id);
  box.classList.add("zr-live");
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => { V = null; box.replaceChildren(...xs.flat().filter(x => x != null && x !== false)); };
  const stop = () => {
    alive = false; clearTimeout(timer); clearInterval(tick); clearInterval(sender);
    window.removeEventListener("resize", onResize);
    box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open");
  };
  window.addEventListener("hashchange", stop, { once: true });
  const onResize = () => { if (V && V.painter) V.painter.resize(); };
  window.addEventListener("resize", onResize);
  const act = async (path, body) => {
    if (busy) return null;
    busy = true;
    try { const x = await api("community/zeichnen/" + path, { method: "POST", body }); st = x; draw(true); return x; }
    catch (e) { toast(e.message, "bad"); return null; }
    finally { busy = false; }
  };
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try {
      let q = "";
      const P = V && V.painter;
      const guesser = st && st.phase === "draw" && !st.me_drawer;
      if (P && (guesser || needStrokes || (st && st.phase === "reveal"))) {
        const c = P.cursor();
        q = "?n=" + c.n + "&pl=" + c.pl + (P.turn != null ? "&t=" + P.turn : "");
      }
      const x = await api("community/zeichnen" + q);
      st = x;
      draw();
    } catch {}
    timer = setTimeout(poll, ZR_POLL_MS);
  }
  const player = id => (st.players || []).find(p => p.id === id) || {};
  const who = id => player(id).name || "?";
  const medal = n => ["🥇", "🥈", "🥉"][n - 1] || n + ".";
  const fill = (key, ...xs) => { let s = I18N.tr(key); xs.forEach((x, i) => { s = s.replace("{" + i + "}", x); }); return s; };

  // ---------- sending the strokes: one request at a time, in order
  function flushStrokes() {
    if (sending || !outq.length || !st || !V || !st.me_drawer || st.phase !== "draw") { if (st && st.phase !== "draw") { outq = []; cur = null; } return; }
    const ops = outq; outq = []; cur = null;
    sending = true;
    api("community/zeichnen/draw", { method: "POST", body: { turn: V.turn, ops } })
      .then(r => { if (r && r.full && !fullWarned) { fullWarned = true; toast(I18N.tr(T("The picture is full – no more lines fit.")), "bad"); } })
      .catch(() => {})
      .finally(() => { sending = false; });
  }

  function draw(force) {
    if (!alive || !box.isConnected) return;
    if (st && !Array.isArray(st.players)) st = null;
    if (st && (st.phase === "draw" || st.phase === "reveal" || st.phase === "choose") && st.left_ms != null) deadlineAt = Date.now() + st.left_ms;
    if (st && V && V.painter && st.strokes) {
      // the drawer only takes the picture of the server when it has nothing yet (e.g. after a reload)
      if (!(st.me_drawer && st.phase === "draw") || !V.painter.events.length) V.painter.merge(st.strokes);
      needStrokes = false;
    }
    const sig = JSON.stringify(st, (k, v) => (k === "left_ms" || k === "strokes" || k === "npts") ? undefined : v);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    if (!st) return show(h("section.card.center", h("div.big-ic", ZR_ICON), h("h2", T("No game right now")), noTableActions("zeichnen", back)));
    sounds();
    if (st.phase !== "lobby") starterBanner(st.starter, "zeichnen");
    if (st.phase === "draw" || st.phase === "reveal") return turnView();
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    if (st.phase === "done") return show(head(), result());
    if (!st.joined && st.phase === "lobby") return show(close, head(), h("section.card.center", h("p", T("Play along on this device?")),
      h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join"))), seats(), hostBar());
    if (st.phase === "lobby") return show(close, head(), h("section.card.center", h("h2", T("Waiting for the start …")),
      h("p.muted", T("Everybody joins on their own device – at least two players.")), seats(), ruleChips(),
      st.coins_on ? h("p.small", "🪙 ", fill(T("Coins for places 1 / 2 / 3: {0}"), zrCoins(st.rewards))) : null), hostBar());
    if (st.phase === "choose") return show(close, head(), choosing(), strip(), hostBar());
    show(close, head(), hostBar());
  }

  function sounds() {
    const found = new Set(st.players.filter(p => p.found).map(p => p.id));
    if (st.phase === "draw" && lastPhase === "draw") {
      for (const id of found) if (!lastFound.has(id)) { try { Sound.play(id === myId ? "done" : "right"); } catch {} }
    }
    if (st.phase !== lastPhase) {
      if (st.phase === "reveal" && lastPhase === "draw" && !st.me_drawer && !st.found_me && st.joined) { try { Sound.play("wrong"); } catch {} }
      if (st.phase === "choose" && st.me_drawer) { try { Sound.play("turn"); navigator.vibrate && navigator.vibrate([60, 40, 60]); } catch {} }
      lastPhase = st.phase;
    }
    lastFound = found;
  }

  // ☰: rules, guests, Skip / End (whoever leads), language – in the header and in the drawing view
  function menu() {
    const lead = isHost() && st.status !== "done";
    const playing = ["choose", "draw", "reveal"].includes(st.phase);
    return gameMenu({ rules: () => zeichnenRulesView(st.rules, st.coins_on ? st.rewards : null),
      invite: !me.guest && st.status !== "done" ? "zeichnen" : null,
      actions: [
        { ic: "⏭", label: T("Skip"), hidden: !lead || !playing, confirm: I18N.tr(T("Skip the turn of {0}?")).replace("{0}", who(st.drawer)), onclick: () => act("skip") },
        { ic: "⏹", label: T("End the game"), danger: true, hidden: !lead, confirm: T("End the game? The points so far count."), onclick: () => act("end") }],
      onLeave: st.status !== "done" ? () => { stop(); back(); } : null });
  }
  function head() {
    return h("div.quiz-head.dm-head.zr-head", h("div.row.head-title", menu(), h("h1", ZR_ICON, " ", zrName())), h("div.row",
      st.phase !== "lobby" && st.phase !== "done" ? h("span.chip", fill(T("Round {0} of {1}"), st.round, st.rounds)) : null));
  }

  function ruleChips() {
    return h("div.sl-chips", h("span.chip", st.category.emoji, " ", zrCat(st.category)),
      h("span.chip", "✏️ ", fill(T("Everybody draws {0}×"), st.rules.rounds)), h("span.chip", "⏱ ", st.rules.time + " s"),
      h("span.chip", st.rules.hints ? "💡 " : "🚫 ", st.rules.hints ? T("Hints on") : T("Hints off")));
  }

  // only the main action (Start) stays as a big button – Skip, End and guests are in ☰
  function hostBar() {
    if (!isHost() || st.status === "done" || st.phase !== "lobby") return null;
    return h("div.row.center.host-bar",
      h("button.btn", { disabled: st.players.length < 2, onclick: begin }, "▶ ", T("Start")));
  }
  async function begin() {
    if (busy) return;
    busy = true;
    try { const r = await beginGame("community/zeichnen/begin", st.players); if (r) { st = r; draw(true); } }
    catch (e) { toast(e.message, "bad"); }
    finally { busy = false; }
  }

  function seats() {
    return h("div.dm-seats", ...st.players.map(p => h("div.dm-seat" + (p.id === myId ? ".dm-me" : ""),
      avatarSvg(p.avatar || {}, 30), C(p.name, "strong.small.dm-name"))));
  }

  // the players with their points: ✏️ draws, ✅ found it
  function strip() {
    return h("div.zr-strip", ...st.players.map(p => h("span.zr-pl" + (p.drawer ? ".zr-is-drawer" : "") + (p.found ? ".zr-is-found" : "") + (p.id === myId ? ".zr-is-me" : ""),
      avatarSvg(p.avatar || {}, 20), C(p.name, "span.zr-pl-name"), h("b", String(p.total)),
      p.drawer ? h("span", "✏️") : p.found ? h("span", "✅") : null)));
  }

  // ---------- choosing the word
  function choosing() {
    clearInterval(tick);
    const secs = h("b.zr-secs");
    const upd = () => { secs.textContent = String(Math.max(0, Math.ceil((deadlineAt - Date.now()) / 1000))); };
    tick = setInterval(upd, 250); upd();
    if (st.me_drawer && st.choices) return h("section.card.center.zr-choose",
      h("h2", "✏️ ", T("Your turn to draw!")), h("p.muted", T("Choose a word:"), " ", secs, " s"),
      h("div.zr-words", ...st.choices.map((w, i) => h("button.btn.big.zr-word", { onclick: () => act("choose", { idx: i }) }, C(w)))),
      h("p.small.muted", T("Only you see the word. Draw it – no letters or numbers!")));
    const p = player(st.drawer);
    return h("section.card.center.zr-choose", avatarSvg(p.avatar || {}, 64),
      h("h2", fill(T("Now choosing a word: {0} …"), who(st.drawer))), h("p.muted", secs, " s"),
      h("p.small.muted", T("Get ready to guess!")));
  }

  // ---------- drawing and guessing (the same canvas through the reveal)
  function turnView() {
    const key = st.game + ":" + st.turn + ":" + (st.me_drawer ? "d" : "g") + (st.joined ? "j" : "");
    if (!V || V.key !== key || !box.contains(V.root)) buildTurn(key);
    updateTurn();
  }

  function buildTurn(key) {
    const drawer = st.me_drawer;
    const canvas = h("canvas.zr-canvas", { "aria-label": I18N.tr(drawer ? T("Your drawing") : T("The drawing")) });
    const wrap = h("div.zr-board", canvas);
    const painter = zrPainter(canvas);
    painter.turn = st.turn;
    needStrokes = true; outq = []; cur = null; fullWarned = false;
    const overlay = h("div.zr-overlay");
    wrap.append(overlay);
    const secs = h("span.zr-secs"), bar = h("i");
    const timeBox = h("div.zr-time", h("div.zr-bar", bar), secs);
    const wordBox = h("div.zr-wordbox");
    const chat = h("div.zr-chat", { "aria-live": "polite" });
    const close = h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕");
    const menuSlot = h("span.zr-menuslot");
    const top = h("div.zr-top", menuSlot, wordBox, timeBox);
    let tools = null, input = null, form = null;
    if (drawer) tools = buildTools(canvas, painter);
    else if (st.joined) {
      input = h("input.zr-input", { type: "text", maxlength: 40, autocomplete: "off", autocapitalize: "off", spellcheck: false, enterkeyhint: "send",
        placeholder: I18N.tr(T("Your guess …")) });
      const send = async () => {
        const text = input.value.trim();
        if (!text) return input.focus();
        input.value = "";
        const x = await act("guess", { text });
        if (x && x.result === "close") toast(I18N.tr(T("Close!")), "good");
        input.focus();
      };
      input.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); send(); } });
      form = h("div.zr-guess", input, h("button.btn", { onclick: send }, "➤"));
    }
    const host = h("div.zr-hostslot"), strip_ = h("div.zr-stripslot");
    const root = h("div.zr-turn" + (drawer ? ".drawing" : ""), top, wrap, tools, form, chat, strip_);
    V = { key, turn: st.turn, root, menuSlot, canvas, painter, overlay, secs, bar, wordBox, chat, input, form, tools, host, strip: strip_, chatSig: "", wordSig: "" };
    box.replaceChildren(close, root, host);
    requestAnimationFrame(() => painter.resize());
    painter.resize();
    clearInterval(tick);
    tick = setInterval(clock, 200);
    clearInterval(sender);
    if (drawer) sender = setInterval(flushStrokes, ZR_SEND_MS);
    if (input && !("ontouchstart" in window)) setTimeout(() => input.focus(), 50);
  }

  function clock() {
    if (!V || !alive) return;
    const left = deadlineAt == null ? 0 : Math.max(0, deadlineAt - Date.now());
    const total = st.phase === "draw" ? (st.time_ms || 1) : 3000;
    V.secs.textContent = st.phase === "draw" ? String(Math.ceil(left / 1000)) : "";
    V.bar.style.width = (st.phase === "draw" ? Math.max(0, Math.min(100, left / total * 100)) : 0) + "%";
    V.root.classList.toggle("hurry", st.phase === "draw" && left < 10000);
  }

  function updateTurn() {
    const reveal = st.phase === "reveal";
    V.root.classList.toggle("reveal", reveal);
    // the word: the drawer and who found it see it, the others the mask with the hint letters
    const wsig = JSON.stringify([st.phase, st.word, st.mask, st.found_me]);
    if (wsig !== V.wordSig) {
      V.wordSig = wsig;
      if (st.word && !reveal) V.wordBox.replaceChildren(h("span.small.muted", st.me_drawer ? T("Draw:") : T("You found it:")), " ", C(st.word, "strong.zr-word-text"));
      else if (st.mask) V.wordBox.replaceChildren(h("span.zr-mask", { translate: "no", "aria-label": fill(T("Letters: {0}"), st.mask.filter(x => x !== " " && x !== "-").length) },
        ...st.mask.map(x => h("span.zr-l" + (x === " " ? ".zr-gap" : x === "_" ? "" : ".zr-hint"), x === "_" ? "" : x))),
        h("small.muted.zr-count", String(st.mask.filter(x => x !== " " && x !== "-").length)));
      else if (reveal) V.wordBox.replaceChildren(h("span.small.muted", T("The word was:")), " ", C(st.word || "?", "strong.zr-word-text"));
    }
    if (V.tools) V.tools.classList.toggle("off", reveal);
    if (V.input) { V.input.disabled = reveal || st.found_me; V.form.classList.toggle("found", !!st.found_me); if (st.found_me) V.input.placeholder = I18N.tr(T("You found it! Wait for the others …")); }
    // the reveal: the word for everybody, the points of the turn
    if (reveal) {
      const pts = st.players.filter(p => p.turn_pts).sort((a, b) => b.turn_pts - a.turn_pts);
      V.overlay.replaceChildren(h("div.zr-reveal",
        h("span.small", st.skipped ? T("Skipped – the word was:") : T("The word was:")), C(st.word || "?", "strong.zr-reveal-word"),
        pts.length ? h("div.zr-reveal-pts", ...pts.map(p => h("span.chip", C(p.name), " +", String(p.turn_pts)))) : h("span.small", T("Nobody guessed it."))));
      V.overlay.classList.add("on");
    } else V.overlay.classList.remove("on");
    const csig = JSON.stringify(st.chat);
    if (csig !== V.chatSig) {
      V.chatSig = csig;
      V.chat.replaceChildren(...(st.chat || []).map(chatLine));
      V.chat.scrollTop = V.chat.scrollHeight;
    }
    V.strip.replaceChildren(strip());
    V.host.replaceChildren(...[hostBar()].filter(Boolean));
    V.menuSlot.replaceChildren(menu());
    clock();
  }

  function chatLine(c) {
    if (c.k === "found") return h("div.zr-msg.found", fill(T("Right guess by {0}! ✅"), who(c.p)), c.p === myId ? h("b", " +" + c.pts) : null);
    if (c.k === "close") return h("div.zr-msg.close", C("«" + c.text + "»"), " ", h("b", T("Close!")), h("small.muted", " ", T("(only you see this)")));
    if (c.k === "mine") return h("div.zr-msg.close", C("«" + c.text + "»"), h("small.muted", " ", T("(only you see this)")));
    return h("div.zr-msg", C(who(c.p), "b"), ": ", C(c.text));
  }

  // ---------- the tools of the drawer: colours, sizes, eraser, undo, clear – and the pointer on the canvas
  function buildTools(canvas, painter) {
    const sw = h("div.zr-colors");
    const sizes = h("div.zr-sizes");
    const drawTools = () => {
      sw.replaceChildren(...ZR_PALETTE.map(c => h("button.zr-sw" + (!tool.e && tool.c === c ? ".on" : ""), { type: "button", style: "background:" + c,
        "aria-label": c, onclick: () => { tool.c = c; tool.e = false; drawTools(); } })));
      sizes.replaceChildren(...[1, 2, 3].map(w => h("button.zr-tool.zr-size" + (tool.w === w ? ".on" : ""), { type: "button", title: I18N.tr(T("Brush size")),
        onclick: () => { tool.w = w; drawTools(); } }, h("i", { style: `width:${4 + w * 5}px;height:${4 + w * 5}px;background:${tool.e ? "#bbb" : tool.c}` }))),
        h("button.zr-tool" + (tool.e ? ".on" : ""), { type: "button", title: I18N.tr(T("Eraser")), onclick: () => { tool.e = !tool.e; drawTools(); } }, "🧽"),
        h("button.zr-tool", { type: "button", title: I18N.tr(T("Undo")), onclick: undo }, "↩️"),
        h("button.zr-tool", { type: "button", title: I18N.tr(T("Clear")), onclick: clear }, "🗑️"));
    };
    const undo = () => { if (!painter.canUndo()) return; painter.op({ u: 1 }); outq.push({ u: 1 }); cur = null; };
    const clear = async () => { if (!painter.canUndo()) return; if (!(await confirmDialog(I18N.tr(T("Clear the whole picture?"))))) return; painter.op({ x: 1 }); outq.push({ x: 1 }); cur = null; };
    drawTools();
    // the pointer: normalised coordinates, three decimals, points closer than a little step are skipped
    let down = null, lastPt = null, count = st.npts || 0;
    const pt = e => {
      const r = canvas.getBoundingClientRect();
      const x = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), y = Math.min(1, Math.max(0, (e.clientY - r.top) / r.height));
      return [Math.round(x * 1000) / 1000, Math.round(y * 1000) / 1000];
    };
    const canDraw = () => st && st.phase === "draw" && st.me_drawer && count < (st.max_points || 30000);
    canvas.addEventListener("pointerdown", e => {
      if (!canDraw() || (e.pointerType === "mouse" && e.button !== 0)) return;
      e.preventDefault();
      try { canvas.setPointerCapture(e.pointerId); } catch {}
      down = e.pointerId;
      const p = pt(e);
      lastPt = p; count++;
      const s = { c: tool.e ? "#000000" : tool.c, w: tool.w, p: p.slice() };
      if (tool.e) s.e = 1;
      painter.start({ ...s, p: p.slice() });
      cur = { ...s, p: p.slice() };
      outq.push(cur);
    });
    canvas.addEventListener("pointermove", e => {
      if (down !== e.pointerId || !canDraw()) return;
      e.preventDefault();
      const evs = e.getCoalescedEvents ? e.getCoalescedEvents() : [e];
      const add = [];
      for (const x of (evs.length ? evs : [e])) {
        const p = pt(x);
        if (Math.hypot(p[0] - lastPt[0], p[1] - lastPt[1]) < 0.004) continue;
        add.push(p[0], p[1]); lastPt = p; count++;
      }
      if (!add.length) return;
      painter.more(add);
      if (!cur) { cur = { p: [] }; outq.push(cur); }
      cur.p.push(...add);
    });
    const up = e => { if (down !== e.pointerId) return; down = null; cur = null; };
    canvas.addEventListener("pointerup", up);
    canvas.addEventListener("pointercancel", up);
    return h("div.zr-tools", sw, sizes);
  }

  // ---------- the end
  function result() {
    clearInterval(tick); clearInterval(sender);
    const mine = player(myId);
    if (mine.place === 1 && !cheered) { cheered = true; confetti(); try { Sound.play("done"); } catch {} }
    const order = (st.ranking || st.players.map(p => p.id)).map(player);
    const winners = st.players.filter(p => p.place === 1).map(p => p.name);
    const log = st.log || [];
    return h("section.card.center.pj-result.zr-result",
      h("h2", "🏆 ", winners.length ? C(winners.join(" & ")) : T("No turn was played")),
      h("p.small.muted", st.category.emoji, " ", zrCat(st.category)),
      h("ol.pk-rank", ...order.map(p => h("li" + (p.id === myId ? ".zr-me" : ""), h("span.pj-medal", p.place ? medal(p.place) : "–"), avatarSvg(p.avatar || {}, 30),
        h("span.grow", C(p.name, "strong")), h("b.sl-total", String(p.total)), p.coins ? h("b.pj-plus", "+" + p.coins + " 🪙") : null))),
      log.length ? h("details.zr-words-log", h("summary.small", fill(T("The words ({0})"), log.length)),
        h("ul.small", ...log.map(e => h("li", C(who(e.drawer), "b"), " ✏️ ", C(e.word, "strong"), h("span.muted", " · " + e.found + " ✅"))))) : null,
      st.coins_on ? null : h("p.small.muted", T("Coins only at a table with at least two people of the family – not for guests.")),
      h("div.row.center", h("button.btn", { onclick: back }, T("Back"))));
  }
  poll();
}

async function zeichnenView() {
  const box = h("div.zr-live");
  screen("games", box);
  zeichnenLive(box, S.profile, () => go("games"));
}

async function zeichnenFamilyCard() {
  const c = S.me && S.me.community, g = c && c.zeichnen;
  return h("section.card.quiz-card", h("h2", ZR_ICON, " ", zrName()),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("zeichnen") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("One draws, the others guess – live on every device. Who guesses fastest gets the most points.")),
         h("button.btn", { onclick: () => zeichnenStartDialog(() => go("zeichnen")) }, "👨‍👩‍👧 ", T("Open a family table"))]);
}
