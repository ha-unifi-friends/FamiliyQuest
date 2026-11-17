// «Stadt-Land-Fluss» – the word game live for the family: everybody writes on their own device, guests via QR code
// (familyquest/stadtland.py). stadtlandLive(box, me, back) runs the family table, stadtlandStartDialog(onStarted) sets
// the categories and the rules. Answers are saved while typing; nobody sees the others' answers before the review.
"use strict";

const SL_ICON = "🏙️";
const slName = () => I18N.tr(T("Stadt-Land-Fluss"));
const slCoins = list => list.join(" / ") + " 🪙";
// the built-in categories in the language of the app (own categories are content and stay as typed)
const SL_CATS = { stadt: T("City"), land: T("Country"), fluss: T("River"), tier: T("Animal"), name: T("First name"), beruf: T("Job"),
  pflanze: T("Plant"), essen: T("Food"), gegenstand: T("Thing"), sport: T("Sport"), ort: T("Swiss place"), farbe: T("Colour"),
  instrument: T("Musical instrument"), koerper: T("Body part"), spielzeug: T("Toy"), getraenk: T("Drink") };
const SL_EMOJI = { stadt: "🏙️", land: "🗺️", fluss: "🌊", tier: "🐾", name: "🙂", beruf: "🧑‍🔧", pflanze: "🌱", essen: "🍝", gegenstand: "🧸",
  sport: "⚽", ort: "🇨🇭", farbe: "🎨", instrument: "🎸", koerper: "🦵", spielzeug: "🪀", getraenk: "🥤" };
const slCatName = c => c.own ? C(c.title) : h("span", I18N.tr(SL_CATS[c.key] || c.title));
const slCatEmoji = c => c.own ? "✏️" : (SL_EMOJI[c.key] || "✏️");
const SL_ARTICLES = new Set(["der", "die", "das", "den", "dem", "des", "le", "la", "les", "l", "il", "lo", "the", "el"]);
// the same check as the server (stadtland.norm / fits): no case, accents, a leading article
function slNorm(s) {
  let w = String(s || "").toLowerCase().replace(/ß/g, "ss").normalize("NFKD").replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, " ").trim().split(" ").filter(Boolean);
  while (w.length > 1 && SL_ARTICLES.has(w[0])) w = w.slice(1);
  return w.join("");
}
const slFits = (s, letter) => { const n = slNorm(s); return !!n && !!letter && n[0] === letter.toLowerCase(); };

function stadtlandRulesView(rules, rewards) {
  const items = [T("A letter is drawn. Find one word per category that starts with it – everybody on their own device."),
    rules && rules.time ? I18N.tr(T("Time per round: {0} seconds.")).replace("{0}", rules.time) : T("The round runs until somebody calls «Stopp!»."),
    rules && rules.stopp ? I18N.tr(T("Who has filled every field may call «Stopp!» – the others get {0} more seconds.")).replace("{0}", 10) : null,
    T("Then everybody sees all answers. Tap 👎 on an answer you think is wrong – it is out when most of the other players say so."),
    T("Points: the only answer in the category 20, an answer nobody else had 10, the same answer as somebody else 5, wrong or empty 0."),
    T("Capitals, accents and an article at the start do not matter: «die Aare» counts for A, «Écosse» for E."),
    rewards ? I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", slCoins(rewards)) : null,
    T("Coins only at a table with at least two people of the family – not for guests.")].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

async function stadtlandStartDialog(onStarted) {
  let r = {};
  try { r = await api("community/stadtland/rules"); } catch {}
  const cats = r.categories || Object.keys(SL_CATS).map(k => ({ key: k }));
  const on = new Set(r.cats || ["stadt", "land", "fluss", "tier", "name", "beruf"]);
  const own = [0, 1].map(i => h("input.sl-own", { type: "text", maxlength: 24, value: (r.own || [])[i] || "", placeholder: I18N.tr(T("Own category (optional)")) }));
  const count = h("p.small.sl-count");
  const grid = h("div.sl-cats");
  const total = () => on.size + own.filter(i => i.value.trim()).length;
  const drawCats = () => {
    grid.replaceChildren(...cats.map(c => h("button.sl-cat" + (on.has(c.key) ? ".on" : ""), { type: "button", "aria-pressed": String(on.has(c.key)),
      onclick: () => { on.has(c.key) ? on.delete(c.key) : on.add(c.key); drawCats(); } },
      h("span.sl-cat-ic", SL_EMOJI[c.key] || "✏️"), slCatName(c))));
    const n = total();
    count.replaceChildren(I18N.tr(T("Chosen: {0} (3 to 8)")).replace("{0}", n));
    count.classList.toggle("bad-text", n < 3 || n > 8);
  };
  own.forEach(i => i.addEventListener("input", drawCats));
  drawCats();
  let rounds = r.rounds || 5;
  const roundSeg = h("div.seg");
  const drawRounds = () => roundSeg.replaceChildren(...[3, 5, 8, 10].map(n => h("button" + (n === rounds ? ".on" : ""), { type: "button", onclick: () => { rounds = n; drawRounds(); } }, String(n))));
  drawRounds();
  const time = h("select", ...[60, 90, 120, 180].map(s => h("option", { value: s, selected: r.time === s }, s + " s")),
    h("option", { value: 0, selected: r.time === 0 }, I18N.tr(T("Until somebody calls «Stopp!»"))));
  if (r.time == null) time.value = "90";
  const stopp = h("input", { type: "checkbox", checked: r.stopp !== false });
  const hard = h("input", { type: "checkbox", checked: !!r.hard });
  const sync = () => { const zero = time.value === "0"; if (zero) stopp.checked = true; stopp.disabled = zero; };
  time.onchange = sync; sync();
  const rw = r.rewards || [0, 0, 0];
  const coins = rw.some(x => x > 0) ? h("p.small.pj-coins", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", slCoins(rw)), h("br"),
    h("span.muted", T("Coins only at a table with at least two people of the family – not for guests."))) : null;
  const m = modal(h("div.form", h("h2", SL_ICON, " ", slName()),
    h("p.small.muted", T("A letter, a few categories, the clock runs – everybody writes on their own device. At least two players.")),
    h("div.field", h("b", T("Categories")), grid, count, h("div.sl-owns", ...own)),
    h("div.grid2", h("div.field", h("b", T("Rounds")), roundSeg), h("label.field", T("Time per round"), time)),
    h("div.cards-rules", h("label.check", stopp, T("«Stopp!»: who has filled every field may call it – the others get 10 more seconds")),
      h("label.check", hard, T("Difficult letters too (C, Q, X, Y)"))),
    coins,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      const n = total();
      if (n < 3 || n > 8) return toast(I18N.tr(T("Choose 3 to 8 categories")), "bad");
      const body = { cats: cats.map(c => c.key).filter(k => on.has(k)), own: own.map(i => i.value.trim()).filter(Boolean),
        rounds, time: +time.value, stopp: stopp.checked, hard: hard.checked };
      try { await api("community/stadtland/start", { method: "POST", body }); m.close(); onStarted(); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
}

function stadtlandLive(box, me, back) {
  let st = null, timer = null, tick = null, alive = true, lastSig = "", cheered = false, busy = false;
  let W = null;                       // the writing view of the current round (kept while the round runs)
  let deadlineAt = null, spinUntil = 0, lockedRound = null, lastStopp = null, lastPhase = null;
  let pending = {}, saveTimer = null;
  const myId = String(me.id);
  box.classList.add("sl-live");
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => { W = null; box.replaceChildren(...xs.flat().filter(x => x != null && x !== false)); };
  const stop = () => { flush(); alive = false; clearTimeout(timer); clearInterval(tick); box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open"); };
  window.addEventListener("hashchange", stop, { once: true });
  document.addEventListener("visibilitychange", () => { if (document.hidden) flush(); });
  const act = async (path, body) => {
    if (busy) return false;
    busy = true;
    try { st = await api("community/stadtland/" + path, { method: "POST", body }); draw(true); return true; }
    catch (e) { toast(e.message, "bad"); return false; }
    finally { busy = false; }
  };
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try { st = await api("community/stadtland"); draw(); } catch {}
    timer = setTimeout(poll, 1000);
  }
  const player = id => (st.players || []).find(p => p.id === id) || {};
  const who = id => player(id).name || "?";
  const medal = n => ["🥇", "🥈", "🥉"][n - 1] || n + ".";
  const fill = (key, ...xs) => { let s = I18N.tr(key); xs.forEach((x, i) => { s = s.replace("{" + i + "}", x); }); return s; };

  // ---------- autosave: changed fields go to the server shortly after typing (and right away at the end)
  function flush() {
    clearTimeout(saveTimer);
    if (!Object.keys(pending).length || !st || st.phase !== "write") { pending = {}; return; }
    const answers = pending; pending = {};
    api("community/stadtland/answers", { method: "POST", body: { answers } }).then(x => { if (x) { st = x; draw(); } }).catch(() => {});
  }
  const queue = (key, value) => { pending[key] = value; clearTimeout(saveTimer); saveTimer = setTimeout(flush, 600); };

  // ---------- the clock: local, from the milliseconds left the server sent
  const locked = () => !!W && (lockedRound === W.key || (deadlineAt != null && Date.now() >= deadlineAt));
  function clock() {
    if (!W || !alive) return;
    const spinning = Date.now() < spinUntil;
    W.letter.classList.toggle("spin", spinning);
    W.letter.textContent = spinning ? "ABDEFGHIKLMNOPRSTUVWZ"[Math.floor(Math.random() * 21)] : st.letter;
    if (!spinning && W.spinning) { W.spinning = false; W.inputs.forEach(i => { i.disabled = locked(); }); if (!locked()) { W.inputs[0].focus(); try { Sound.play("right"); } catch {} } }
    const left = deadlineAt == null ? null : Math.max(0, deadlineAt - Date.now());
    const total = st.stopp ? (st.grace || 10) * 1000 : (st.time_ms || 1);
    const frac = left == null ? 1 : Math.max(0, Math.min(1, left / total));
    W.arc.style.strokeDashoffset = String(W.circ * (1 - frac));
    W.ring.classList.toggle("hurry", left != null && left < 10000);
    W.secs.textContent = left == null ? "∞" : String(Math.ceil(left / 1000));
    if (left === 0 && lockedRound !== W.key) {
      lockedRound = W.key;
      flush();
      W.inputs.forEach(i => { i.disabled = true; i.blur(); });
      W.stopBtn && (W.stopBtn.disabled = true);
      W.msg.replaceChildren(h("strong", "⏰ ", T("Time is up!")), " ", h("span.muted", T("The answers are being checked …")));
      try { Sound.play("wrong"); } catch {}
    }
  }

  function draw(force) {
    if (!alive || !box.isConnected) return;
    if (st && !Array.isArray(st.players)) st = null;
    // the clock fields change every second – they alone do not draw the view again
    const sig = JSON.stringify(st, (k, v) => (k === "left_ms" || k === "spin_ms") ? undefined : v);
    if (st && st.phase === "write") {
      if (st.left_ms != null) deadlineAt = Date.now() + st.left_ms; else deadlineAt = null;
    }
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    if (!st) return show(h("section.card.center", h("div.big-ic", SL_ICON), h("h2", T("No game right now")), h("button.btn", { onclick: back }, T("Back"))));
    if (st.phase !== lastPhase) {
      if (lastPhase && st.phase === "scores") { const mine = (st.last && st.last.points || {})[myId]; try { Sound.play(mine ? "right" : "wrong"); } catch {} }
      lastPhase = st.phase;
    }
    if (st.phase === "write" && st.joined) return writing();
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    if (st.phase === "done") return show(head(), result());
    if (!st.joined) return show(close, head(), h("section.card.center",
      h("p", st.phase === "lobby" ? T("Play along on this device?") : T("The game is running – you watch.")),
      st.phase === "lobby" ? h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join")) : null), seats(), hostBar());
    if (st.phase === "lobby") return show(close, head(), h("section.card.center", h("h2", T("Waiting for the start …")),
      h("p.muted", T("Everybody joins on their own device – at least two players.")), seats(), catChips(),
      st.coins_on ? h("p.small", "🪙 ", fill(T("Coins for places 1 / 2 / 3: {0}"), slCoins(st.rewards))) : null), hostBar());
    if (st.phase === "review") return show(close, head(), review(), hostBar());
    if (st.phase === "scores") return show(close, head(), scores(), hostBar());
    show(close, head(), hostBar());
  }

  // ☰: rules, guests, Close the round / End (whoever leads), language – in the header and in the writing view
  function menu() {
    const lead = isHost() && st.status !== "done";
    return gameMenu({ rules: () => stadtlandRulesView(st.rules, st.coins_on ? st.rewards : null),
      invite: !me.guest && st.status !== "done" ? "stadtland" : null,
      actions: [
        { ic: "⏭", label: T("Close the round"), hidden: !lead || st.phase !== "write", confirm: T("Close the writing for everybody now?"),
          onclick: () => { if (st.phase === "write") { flush(); act("next"); } } },
        { ic: "⏹", label: T("End the game"), danger: true, hidden: !lead, confirm: T("End the game? The rounds so far count."), onclick: () => { flush(); act("end"); } }],
      onLeave: st.status !== "done" ? () => { stop(); back(); } : null });
  }
  function head() {
    return h("div.quiz-head.dm-head.sl-head", h("div.row.head-title", menu(), h("h1", SL_ICON, " ", slName())));
  }

  // only the main action of the moment stays as a big button (Start, Go on, Next round) – the rest is in ☰
  function hostBar() {
    if (!isHost() || st.status === "done") return null;
    const nextLabel = { review: T("Go on"), scores: st.round >= st.rounds ? T("Results") : T("Next round") }[st.phase];
    if (st.phase !== "lobby" && !nextLabel) return null;
    return h("div.row.center.host-bar",
      st.phase === "lobby" ? h("button.btn", { disabled: st.players.length < 2, onclick: () => act("begin") }, "▶ ", T("Start")) : null,
      nextLabel ? h("button.btn", { onclick: () => { flush(); act("next"); } }, "⏭ ", nextLabel) : null);
  }

  function catChips() {
    return h("div.sl-chips", ...(st.cats.length ? st.cats : (st.rules.cats || []).map(k => ({ key: k })).concat((st.rules.own || []).map(t => ({ key: "", title: t, own: true }))))
      .map(c => h("span.chip", slCatEmoji(c), " ", slCatName(c))));
  }

  function seats() {
    return h("div.dm-seats", ...st.players.map(p => h("div.dm-seat" + (p.id === myId ? ".dm-me" : ""),
      avatarSvg(p.avatar || {}, 30), C(p.name, "strong.small.dm-name"))));
  }

  // ---------- writing: the letter, the clock, one field per category
  function writing() {
    const key = st.game + ":" + st.round;
    if (!W || W.key !== key || !box.contains(W.root)) buildWriting(key);
    updateWriting();
  }

  function buildWriting(key) {
    const mine = st.mine || {};
    pending = {};
    spinUntil = Date.now() + (st.spin_ms || 0);
    const size = 64, stroke = 7, rr = (size - stroke) / 2, circ = 2 * Math.PI * rr;
    const ringBox = h("div.sl-ring");
    ringBox.innerHTML = `<svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" aria-hidden="true">
      <circle cx="${size / 2}" cy="${size / 2}" r="${rr}" fill="none" stroke="var(--ring-bg)" stroke-width="${stroke}"/>
      <circle class="sl-arc" cx="${size / 2}" cy="${size / 2}" r="${rr}" fill="none" stroke="currentColor" stroke-width="${stroke}" stroke-linecap="round"
        stroke-dasharray="${circ}" stroke-dashoffset="0" transform="rotate(-90 ${size / 2} ${size / 2})"/></svg>`;
    const secs = h("span.sl-secs");
    ringBox.append(secs);
    const letter = h("div.sl-letter", { "aria-live": "polite" }, st.letter);
    const inputs = st.cats.map((c, i) => {
      const inp = h("input.sl-input", { type: "text", maxlength: 40, value: mine[c.key] || "", autocomplete: "off", autocapitalize: "words", spellcheck: false,
        enterkeyhint: i === st.cats.length - 1 ? "done" : "next", "aria-label": c.own ? c.title : I18N.tr(SL_CATS[c.key] || c.title) });
      inp.dataset.key = c.key;
      inp.addEventListener("input", () => { queue(c.key, inp.value); mark(); });
      inp.addEventListener("keydown", e => {
        if (e.key !== "Enter") return;
        e.preventDefault();
        const next = inputs.slice(i + 1).concat(inputs.slice(0, i)).find(x => !x.value.trim());
        if (next && i < inputs.length - 1) inputs[i + 1].focus(); else if (next) next.focus(); else { inp.blur(); flush(); }
      });
      return inp;
    });
    const rows = st.cats.map((c, i) => h("label.sl-row", h("span.sl-cat-name", h("span.sl-cat-ic", slCatEmoji(c)), slCatName(c)), inputs[i], h("span.sl-ok")));
    const stopBtn = st.rules.stopp ? h("button.btn.big.sl-stopp", { onclick: callStopp }, "✋ ", T("Stopp!")) : null;
    const msg = h("div.sl-msg");
    const fin = h("span.sl-fin");
    const host = h("div.sl-hostslot"), menuSlot = h("span.sl-menuslot");
    const close = h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕");
    const root = h("div.sl-write",
      h("div.sl-top", menuSlot, letter, h("div.sl-info", h("span.chip", fill(T("Round {0} of {1}"), st.round, st.rounds)), fin), ringBox),
      msg, h("div.sl-fields", ...rows), stopBtn, host);
    W = { key, root, inputs, rows, letter, ring: ringBox, arc: ringBox.querySelector(".sl-arc"), circ, secs, stopBtn, msg, fin, host, menuSlot, spinning: Date.now() < spinUntil };
    lockedRound = lockedRound === key ? key : null;
    inputs.forEach(i => { i.disabled = W.spinning || locked(); });
    box.replaceChildren(close, root);
    lastStopp = st.stopp ? st.stopp.by : null;
    mark();
    clearInterval(tick);
    tick = setInterval(clock, 200);
    clock();
  }

  function mark() {
    if (!W) return;
    let all = true;
    W.inputs.forEach((inp, i) => {
      const v = inp.value.trim(), ok = slFits(v, st.letter);
      if (!ok) all = false;
      W.rows[i].classList.toggle("ok", ok);
      W.rows[i].classList.toggle("bad", !!v && !ok);
      W.rows[i].lastChild.textContent = ok ? "✓" : v ? "✗" : "";
    });
    if (W.stopBtn) W.stopBtn.disabled = !all || !!st.stopp || locked();
  }

  async function callStopp() {
    if (!W || busy) return;
    clearTimeout(saveTimer); pending = {};
    const answers = Object.fromEntries(W.inputs.map(i => [i.dataset.key, i.value]));
    if (await act("stopp", { answers })) { try { Sound.play("right"); } catch {} }
  }

  function updateWriting() {
    const n = st.players.length;
    W.fin.replaceChildren(fill(T("Finished: {0} of {1}"), st.finished || 0, n));
    if (st.stopp && st.stopp.by !== lastStopp) {
      lastStopp = st.stopp.by;
      if (st.stopp.by !== myId) { try { Sound.play("wrong"); } catch {} }
    }
    if (lockedRound !== W.key) {
      W.msg.replaceChildren(st.stopp
        ? h("strong.sl-stopped", "✋ ", st.stopp.by === myId ? T("You called «Stopp!»") : fill(T("«Stopp!» from {0}"), who(st.stopp.by)), " – ",
          h("span", fill(T("Still {0} seconds"), st.grace || 10)))
        : h("span.muted.small", deadlineAt == null ? T("Write until somebody calls «Stopp!» – your answers are saved as you type.") : T("Your answers are saved as you type.")));
    }
    W.root.classList.toggle("stopped", !!st.stopp);
    W.host.replaceChildren(...[hostBar()].filter(Boolean));
    W.menuSlot.replaceChildren(menu());
    mark();
    clock();
  }

  // ---------- review: all answers per category, 👎 for the others, who leads decides
  function review() {
    const rv = st.review || {};
    const lead = isHost();
    const meP = player(myId);
    const readyN = st.players.filter(p => p.ready).length;
    const cards = st.cats.map(c => {
      const row = rv[c.key] || {};
      return h("section.card.sl-rv", h("h3", slCatEmoji(c), " ", slCatName(c)),
        h("div.sl-rv-list", ...st.players.map(p => {
          const x = row[p.id] || {};
          const own = p.id === myId, text = (x.text || "").trim();
          const cls = (x.valid ? ".valid" : ".invalid") + (own ? ".mine" : "");
          const why = !text ? T("empty") : !x.auto && x.override == null ? T("wrong letter") : null;
          return h("div.sl-ans" + cls,
            h("span.sl-who", avatarSvg(p.avatar || {}, 22), C(p.name, "span.small.sl-name")),
            h("span.sl-text", text ? C(text) : h("span.muted", "–"), why ? h("small.muted", " (", why, ")") : null,
              x.override != null ? h("small.sl-ov", x.override ? " ✓ " : " ✗ ", T("decided")) : null),
            h("span.sl-acts",
              !own && text && x.auto ? h("button.sl-thumb" + (x.mine_reject ? ".on" : ""), { title: T("Not valid"), "aria-pressed": String(!!x.mine_reject),
                onclick: () => act("vote", { target: p.id, cat: c.key, reject: !x.mine_reject }) }, "👎", x.rejects && x.rejects.length ? h("small", " " + x.rejects.length) : null)
                : (x.rejects && x.rejects.length ? h("small.muted", "👎 " + x.rejects.length) : null),
              lead && text ? h("span.sl-lead",
                h("button.sl-ovb" + (x.override === true ? ".on" : ""), { title: T("Valid"), onclick: () => act("override", { target: p.id, cat: c.key, valid: x.override === true ? null : true }) }, "✓"),
                h("button.sl-ovb.no" + (x.override === false ? ".on" : ""), { title: T("Not valid"), onclick: () => act("override", { target: p.id, cat: c.key, valid: x.override === false ? null : false }) }, "✗")) : null,
              h("b.sl-pts" + (x.pts ? "" : ".zero"), String(x.pts || 0))));
        })));
    });
    const myPts = (st.round_points || {})[myId];
    return h("div.sl-review",
      h("div.sl-rv-head", h("div.sl-letter.small", st.letter), h("div",
        h("strong", T("Check the answers")), h("span.small.muted", " · ", fill(T("Round {0} of {1}"), st.round, st.rounds)), h("br"),
        h("span.small.muted", T("Tap 👎 on answers that are not valid – most of the others decide.")))),
      ...cards,
      h("section.card.sl-rv-foot",
        st.joined ? h("div.row.center", myPts != null ? h("span.chip", fill(T("This round: {0} points"), myPts)) : null,
          h("button.btn" + (meP.ready ? ".ghost" : ".big"), { onclick: () => act("ready", { ready: !meP.ready }) }, meP.ready ? "↩ " : "✔ ", meP.ready ? T("Not done yet") : T("Done"))) : null,
        h("p.small.muted.center", fill(T("Done: {0} of {1}"), readyN, st.players.length))));
  }

  // ---------- between the rounds: the scoreboard (with the answers of the last round)
  function board(withRound) {
    const order = st.players.slice().sort((a, b) => b.total - a.total);
    const last = st.last || {};
    let place = 0, prev = null;
    return h("ol.pk-rank.sl-board", ...order.map((p, i) => {
      if (p.total !== prev) { place = i + 1; prev = p.total; }
      const pl = st.phase === "done" ? (p.place || place) : place;
      return h("li" + (p.id === myId ? ".me" : ""), h("span.pj-medal", medal(pl)), avatarSvg(p.avatar || {}, 30),
        h("span.grow", C(p.name, "strong")),
        withRound && last.points ? h("span.small.muted", "+" + (last.points[p.id] || 0)) : null,
        h("b.sl-total", String(p.total)), p.coins ? h("b.pj-plus", "+" + p.coins + " 🪙") : null);
    }));
  }

  function lastAnswers() {
    const last = st.last;
    if (!last || !last.answers) return null;
    return h("details.sl-last", h("summary.small", fill(T("Answers of round {0} ({1})"), last.n, last.letter)),
      h("div.sl-table-wrap", h("table.sl-table",
        h("thead", h("tr", h("th", ""), ...st.players.map(p => h("th", C(p.name))))),
        h("tbody", ...st.cats.map(c => h("tr", h("th", slCatEmoji(c), " ", slCatName(c)),
          ...st.players.map(p => { const x = (last.answers[c.key] || {})[p.id] || {};
            return h("td" + (x.valid ? "" : ".invalid"), x.text ? C(x.text) : "–", h("small", " " + (x.pts || 0))); })))))));
  }

  function scores() {
    const lead = isHost();
    return h("section.card.center.sl-scores",
      h("h2", "📊 ", fill(T("After round {0} of {1}"), st.round, st.rounds)),
      h("p.small.muted", T("Letters so far:"), " ", h("b", (st.letters || []).join(" "))),
      board(true), lastAnswers(),
      lead ? null : h("p.muted", T("Waiting for the next round …")));
  }

  function result() {
    const mine = player(myId);
    if (mine.place === 1 && !cheered) { cheered = true; confetti(); try { Sound.play("done"); } catch {} }
    const winners = st.players.filter(p => p.place === 1).map(p => p.name);
    return h("section.card.center.pj-result.sl-result",
      h("h2", "🏆 ", winners.length ? C(winners.join(" & ")) : T("No round was played")),
      st.log && st.log.length ? h("p.small.muted", fill(T("Rounds: {0} · letters {1}"), st.log.length, st.log.map(e => e.letter).join(" "))) : null,
      board(false), lastAnswers(),
      st.coins_on ? null : h("p.small.muted", T("Coins only at a table with at least two people of the family – not for guests.")),
      h("div.row.center", h("button.btn", { onclick: back }, T("Back"))));
  }
  poll();
}

async function stadtlandView() {
  const box = h("div.sl-live");
  screen("games", box);
  stadtlandLive(box, S.profile, () => go("games"));
}

async function stadtlandFamilyCard() {
  const c = S.me && S.me.community, g = c && c.stadtland;
  return h("section.card.quiz-card", h("h2", SL_ICON, " ", slName()),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("stadtland") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("The word game: a letter, a few categories, the clock runs – everybody writes on their own device.")),
         h("button.btn", { onclick: () => stadtlandStartDialog(() => go("stadtland")) }, "👨‍👩‍👧 ", T("Open a family table"))]);
}
