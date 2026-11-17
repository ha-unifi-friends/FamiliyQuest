// Etappe H – community in the learning app: family quiz (live), family council, personal history.
// Uses kid.js (screen, go, S) and shared/ui.js (h, api, toast, avatarSvg, confetti). Loaded before kid.js.
"use strict";

const QUIZ_COLORS = ["var(--ans-1)", "var(--ans-2)", "var(--ans-3)", "var(--ans-4)"];     // same as the learning tiles
const QUIZ_SHAPES = ["♠\uFE0E", "♥\uFE0E", "♦\uFE0E", "♣\uFE0E"];   // \uFE0E: as text, not as emoji
const onlyEmoji = s => /^[\p{Extended_Pictographic}\p{Regional_Indicator}\u200d\ufe0f\s]+$/u.test(s || ""); // flags as answers: show them big

// ---------------------------------------------------------------- start page: banners
function communityBanners(c) {
  if (!c) return [];
  const out = [];
  if (c.quiz && c.quiz.status !== "done") out.push(h("button.card.banner.quiz-banner", { onclick: () => go("quiz") },
    h("span.big-ic", "🎯"), h("span.grow", h("strong", T("Family quiz")), " ", C("«" + c.quiz.title + "»"), h("br"),
      h("span.small", c.quiz.joined ? T("You are in – let's go!") : T("is running – join in!"))), h("span.big-ic", "➜")));
  if (c.bingo) out.push(h("button.card.banner.quiz-banner", { onclick: () => go("bingo") },
    h("span.big-ic", "🎱"), h("span.grow", h("strong", "Bingo"), h("br"),
      h("span.small", c.bingo.joined ? T("You are in – let's go!") : T("is running – join in!"))), h("span.big-ic", "➜")));
  for (const k of ["tschau", "karussell"]) if (c[k]) out.push(h("button.card.banner.quiz-banner", { onclick: () => go(k) },
    h("span.big-ic", k === "tschau" ? "🂡" : "🎠"), h("span.grow", h("strong", k === "tschau" ? "Tschau Sepp" : "Kartenkarussell"), h("br"),
      h("span.small", c[k].joined ? T("You are in – let's go!") : T("is running – join in!"))), h("span.big-ic", "➜")));
  if (c.domino) out.push(h("button.card.banner.quiz-banner", { onclick: () => go("domino") },
    h("span.big-ic", "🁫"), h("span.grow", h("strong", "Domino"), h("br"),
      h("span.small", c.domino.joined ? T("You are in – let's go!") : T("is running – join in!"))), h("span.big-ic", "➜")));
  if (c.paarjagd) out.push(h("button.card.banner.quiz-banner", { onclick: () => go("paarjagd") },
    h("span.big-ic", "🧠"), h("span.grow", h("strong", T("Paarjagd")), h("br"),
      h("span.small", c.paarjagd.joined ? T("You are in – let's go!") : T("is running – join in!"))), h("span.big-ic", "➜")));
  if (c.werbinich) out.push(h("button.card.banner.quiz-banner", { onclick: () => go("werbinich") },
    h("span.big-ic", "🎭"), h("span.grow", h("strong", T("Wer bin ich?")), h("br"),
      h("span.small", c.werbinich.joined ? T("You are in – let's go!") : T("is running – join in!"))), h("span.big-ic", "➜")));
  if (c.kartenlauf) out.push(h("button.card.banner.quiz-banner", { onclick: () => go("kartenlauf") },
    h("span.big-ic", "🏁"), h("span.grow", h("strong", "Kartenlauf"), h("br"),
      h("span.small", c.kartenlauf.joined ? T("You are in – let's go!") : T("is running – join in!"))), h("span.big-ic", "➜")));
  if (c.stadtland) out.push(h("button.card.banner.quiz-banner", { onclick: () => go("stadtland") },
    h("span.big-ic", "🏙️"), h("span.grow", h("strong", T("Stadt-Land-Fluss")), h("br"),
      h("span.small", c.stadtland.joined ? T("You are in – let's go!") : T("is running – join in!"))), h("span.big-ic", "➜")));
  if (c.zeichnen) out.push(h("button.card.banner.quiz-banner", { onclick: () => go("zeichnen") },
    h("span.big-ic", "🎨"), h("span.grow", h("strong", T("Zeichnen & Raten")), h("br"),
      h("span.small", c.zeichnen.joined ? T("You are in – let's go!") : T("is running – join in!"))), h("span.big-ic", "➜")));
  if (c.wuerfel) out.push(h("button.card.banner.quiz-banner", { onclick: () => go("wuerfel") },
    h("span.big-ic", "🎲"), h("span.grow", h("strong", T("Fünf Würfel")), h("br"),
      h("span.small", c.wuerfel.joined ? T("You are in – let's go!") : T("is running – join in!"))), h("span.big-ic", "➜")));
  if (c.heimwaerts) out.push(h("button.card.banner.quiz-banner", { onclick: () => go("heimwaerts") },
    h("span.big-ic", "🏠"), h("span.grow", h("strong", T("Heimwärts")), h("br"),
      h("span.small", c.heimwaerts.joined ? T("You are in – let's go!") : T("is running – join in!"))), h("span.big-ic", "➜")));
  if (c.jump) out.push(h("button.card.banner.quiz-banner", { onclick: () => go("jump") },
    h("span.big-ic", "🦘"), h("span.grow", h("strong", "Jump"), h("br"),
      h("span.small", c.jump.joined ? T("You are in – let's go!") : T("is running – join in!"))), h("span.big-ic", "➜")));
  if (c.klatsch) out.push(h("button.card.banner.quiz-banner", { onclick: () => { try { KbAudio.ensure(); } catch {} go("klatsch"); } },
    h("span.big-ic", "👏"), h("span.grow", h("strong", T("Klatsch den Beat")), h("br"),
      h("span.small", c.klatsch.joined ? T("You are in – let's go!") : T("is running – join in!"))), h("span.big-ic", "➜")));
  if (c.verboten) out.push(h("button.card.banner.quiz-banner", { onclick: () => go("verboten") },
    h("span.big-ic", "🚫"), h("span.grow", h("strong", T("Verbotene Wörter")), h("br"),
      h("span.small", c.verboten.joined ? T("You are in – let's go!") : T("is running – join in!"))), h("span.big-ic", "➜")));
  if (c.jass) out.push(h("button.card.banner.quiz-banner", { onclick: () => go("jass") },
    h("span.big-ic", "♣️"), h("span.grow", h("strong", T("Jass")), h("br"),
      h("span.small", c.jass.joined ? T("You are in – let's go!") : T("is running – join in!"))), h("span.big-ic", "➜")));
  if (c.werwolf) out.push(h("button.card.banner.quiz-banner", { onclick: () => go("werwolf") },
    h("span.big-ic", "🐺"), h("span.grow", h("strong", T("Werwölfe")), h("br"),
      h("span.small", c.werwolf.joined ? T("You are in – let's go!") : T("is running – join in!"))), h("span.big-ic", "➜")));
  if (c.schach) out.push(h("button.card.banner.quiz-banner", { onclick: () => go("schach/" + c.schach.game) },
    h("span.big-ic", "♟️"), h("span.grow", h("strong", T("Chess")), h("br"),
      h("span.small", c.schach.my_turn ? T("Your move!") : I18N.tr(T("{0} invites you to a game")).replace("{0}", c.schach.from || "?"))), h("span.big-ic", "➜")));
  if (c.dorfmarkt) out.push(h("button.card.banner.quiz-banner", { onclick: () => go("dorfmarkt") },
    h("span.big-ic", "🏘️"), h("span.grow", h("strong", T("Dorfmarkt")), h("br"),
      h("span.small", c.dorfmarkt.joined ? T("You are in – let's go!") : T("is running – join in!"))), h("span.big-ic", "➜")));
  if (c.song) out.push(h("button.card.banner.quiz-banner", { onclick: () => go("song") },
    h("span.big-ic", "🎵"), h("span.grow", h("strong", T("Guess the song")), h("br"),
      h("span.small", c.song.joined ? T("You are in – let's go!") : T("is running – join in!"))), h("span.big-ic", "➜")));
  if (c.poker) out.push(h("button.card.banner.quiz-banner", { onclick: () => go("poker") },
    h("span.big-ic", "🃏"), h("span.grow", h("strong", "Texas Hold'em"), h("br"),
      h("span.small", c.poker.joined ? T("You are in – let's go!") : T("is running – join in!"))), h("span.big-ic", "➜")));
  if (c.polls_open) out.push(h("button.card.banner", { onclick: () => go("family") },
    h("span.big-ic", "📊"), h("span.grow", h("strong", T("Polls")), h("br"),
      h("span.small", I18N.tr(T("Your answer is missing: {0}")).replace("{0}", c.polls_open))), h("span.big-ic", "➜")));
  if (c.votes_open) out.push(h("button.card.banner", { onclick: () => go("family") },
    h("span.big-ic", "🗳️"), h("span.grow", h("strong", T("Family council")), h("br"),
      h("span.small", I18N.tr(T("Your vote is missing: {0}")).replace("{0}", c.votes_open))), h("span.big-ic", "➜")));
  return out;
}

// ---------------------------------------------------------------- family quiz (live)
async function quizView() {
  const box = h("div.quiz-live");
  screen("games", box);
  quizLive(box, S.profile, () => go("games"));
}

// pictures of questions: a canton as outline or marked on the map (geo/ch.json, loaded once)
let CH_GEO = null;
let ARMS = null;
function questionImage(img) {
  if (!img) return null;
  // a flag, a big emoji or an own drawing (SVG as an image – nothing in it can run)
  if (img.flag) return h("div.q-img.q-flag", h("img", { src: `flags/${img.flag}.svg`, alt: "", draggable: false }));
  if (img.emoji) return h("div.q-img.q-emoji", img.emoji);
  if (img.svg) return h("div.q-img.q-svg", h("img", { src: "data:image/svg+xml;charset=utf-8," + encodeURIComponent(img.svg), alt: "", draggable: false }));
  if (img.geo !== "canton") return null;
  const box = h("div.q-img");
  if (img.mode === "arms") {               // coats of arms as vector drawings in a shield (geo/arms.json, tools/build_arms.py)
    ARMS = ARMS || fetch("geo/arms.json").then(r => r.json());
    ARMS.then(a => { if (!a.arms[img.id]) return; box.classList.add("arms");
      const id = "arms-clip-" + Math.random().toString(36).slice(2, 8);
      box.innerHTML = `<svg viewBox="-2 -2 ${a.width + 4} ${a.height + 4}" role="img"><defs><clipPath id="${id}"><path d="${a.shield}"/></clipPath></defs>`
        + `<g clip-path="url(#${id})">${a.arms[img.id]}</g><path d="${a.shield}" fill="none" stroke="rgba(0,0,0,.55)" stroke-width="1.6"/></svg>`; }).catch(() => {});
    return box;
  }
  const draw = g => {
    const c = g.cantons[img.id]; if (!c) return;
    const NS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(NS, "svg");
    const path = (d, cls) => { const e = document.createElementNS(NS, "path"); e.setAttribute("d", d); e.setAttribute("class", cls); return e; };
    if (img.mode === "map") {
      svg.setAttribute("viewBox", `0 0 ${g.width} ${g.height}`);
      for (const [k, x] of Object.entries(g.cantons)) svg.append(path(x.d, k === img.id ? "geo-c on" : "geo-c"));
      for (const d of g.lakes) svg.append(path(d, "geo-lake"));
    } else {
      const [x0, y0, x1, y1] = c.bbox, pad = Math.max(x1 - x0, y1 - y0) * 0.06;
      svg.setAttribute("viewBox", `${x0 - pad} ${y0 - pad} ${x1 - x0 + 2 * pad} ${y1 - y0 + 2 * pad}`);
      svg.append(path(c.d, "geo-c on"));
    }
    svg.setAttribute("role", "img");
    box.replaceChildren(svg);
  };
  CH_GEO = CH_GEO || fetch("geo/ch.json").then(r => r.json());
  CH_GEO.then(draw).catch(() => {});
  return box;
}

// maps for pin questions: Switzerland (cantons, lakes) or Europe (countries); pins are lat/lon
const GEO = {};
function loadGeo(name) { GEO[name] = GEO[name] || fetch(`geo/${name === "ch" ? "ch" : "europe"}.json`).then(r => r.json()); return GEO[name]; }
function geoMap(name, { pick, pins = [], target = null } = {}) {
  const NS = "http://www.w3.org/2000/svg";
  const box = h("div.q-map" + (pick ? ".pick" : "") + (target ? ".reveal" : ""));
  loadGeo(name).then(g => {
    const P = g.proj, xy = (lat, lon) => [(lon - P.lon0) * P.k * P.scale, (P.lat1 - lat) * P.scale];
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", `0 0 ${g.width} ${g.height}`);
    const el = (t, a) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); return e; };
    if (name === "ch") { for (const c of Object.values(g.cantons)) svg.append(el("path", { d: c.d, class: "geo-c" })); for (const d of g.lakes) svg.append(el("path", { d, class: "geo-lake" })); }
    else { svg.append(el("rect", { x: -50, y: -50, width: g.width + 100, height: g.height + 100, class: "geo-sea" })); for (const c of g.countries) svg.append(el("path", { d: c.d, class: "geo-c" })); }
    const layer = el("g", {}); svg.append(layer);
    const r = g.width / 90;
    const drawPins = list => {
      layer.replaceChildren();
      if (target) {
        const [tx, ty] = xy(target.lat, target.lon);
        for (const p of list) { const [px, py] = xy(p.lat, p.lon); layer.append(el("line", { x1: tx, y1: ty, x2: px, y2: py, class: "geo-line" })); }
        layer.append(el("circle", { cx: tx, cy: ty, r: r * 1.3, class: "geo-target" }));
      }
      list.forEach((p, i) => {
        const [px, py] = xy(p.lat, p.lon);
        layer.append(el("circle", { cx: px, cy: py, r, class: "geo-pin" + (p.me ? " me" : "") }));
        if (p.name) { const t = el("text", { x: px + r * 1.4, y: py + r * 0.5, class: "geo-label", "font-size": r * 2.2 }); t.textContent = p.name; layer.append(t); }
      });
    };
    drawPins(pins);
    if (pick) svg.addEventListener("click", e => {
      const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
      const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
      const lon = loc.x / (P.k * P.scale) + P.lon0, lat = P.lat1 - loc.y / P.scale;
      drawPins([{ lat, lon, me: true }]); pick(lat, lon);
    });
    box.replaceChildren(svg);
  }).catch(() => {});
  return box;
}

// guests: who leads a game opens an invitation – a QR code for the phones of friends and grandparents
async function guestInvite(game, gid) {
  let r;
  try { r = await api("community/guests", { method: "POST", body: { game, on: true, gid } }); } catch (e) { return toast(e.message, "bad"); }
  const a = r.access || {};
  const host = (a.ips && a.ips[0]) || location.hostname;
  const url = `http://${host}:${a.port || a.default_port || 8099}/gast?c=${encodeURIComponent(r.invite.code)}`;
  const field = h("input", { type: "url", readonly: true, value: url, onfocus: e => e.target.select() });
  const m = modal(h("div.form.center",
    h("h2", "👥 ", T("Invite guests")),
    h("p", T("Guests scan the code with their phone in our home network, type their name and play along.")),
    !a.enabled && a.port == null ? h("p.warn-text", T("Direct access is still off: in Home Assistant open the app → Configuration, switch on direct_access and restart the app.")) : null,
    h("div.qr-box.guest-qr", qrSvg(url)), field,
    h("div.row.center", h("button.btn", { onclick: () => m.close() }, T("Close")),
      h("button.btn.ghost", { onclick: async () => { await api("community/guests", { method: "POST", body: { game, on: false, gid } }); toast(T("Invitation closed"), "good"); m.close(); } }, "🚪 ", T("Close the invitation")))));
}

// the live game in `box` for profile `me` (learning app and parent area); `back` leaves it
function quizLive(box, me, back) {
  let last = "", timer = null, alive = true, tick = null;
  let input = { idx: -1 };          // my estimate / pin of the current question – kept when the view is drawn again
  const isHost = st => st.host === me.id || me.role === "parent";
  // a running quiz fills the page (an overlay over the menus – not the browser's full-screen mode)
  const full = on => {
    box.classList.toggle("quiz-full", on);
    document.body.classList.toggle("quiz-open", on);
  };
  const closeBtn = () => h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { full(false); stop(); back(); } }, "✕");
  const show = (...xs) => {
    const items = xs.flat().filter(x => x != null && x !== false);
    const running = !!last && !last.startsWith("null");      // the result is shown full screen too
    full(running);
    box.replaceChildren(...(running ? [closeBtn()] : []), ...items);
  };
  const stop = () => { alive = false; clearTimeout(timer); clearInterval(tick); box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open"); };
  window.addEventListener("hashchange", stop, { once: true });
  const act = async (path, body) => {
    try {
      const st = await api("community/quiz/" + path, { method: "POST", body });
      if (path === "abort") { full(false); stop(); return back(); }      // stopped: leave the game
      draw(st);
    } catch (e) { toast(e.message, "bad"); }
  };
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try { draw(await api("community/quiz")); } catch {}
    timer = setTimeout(poll, 800);
  }
  function draw(st) {
    if (!alive || !box.isConnected) return;                            // the game was left meanwhile: a late answer
    if (st && !Array.isArray(st.players)) st = null;                   // an answer that is not a game state: no game
    const sig = JSON.stringify(st && [st.status, st.idx, st.joined, st.my_choice, (st.answered || []).length, st.players.map(p => p.id + ":" + p.points)]);
    if (sig === last) return;
    last = sig;
    clearInterval(tick);
    if (!st) return show(h("section.card.center", h("div.big-ic", "🎯"), h("h2", T("No family quiz right now")),
      h("p.muted", T("Start one from the list of quizzes – everybody can join on their own device.")), h("button.btn", { onclick: back }, T("Back"))));
    // ☰: guests (everybody of the family), stop for whoever leads, language
    const menu = gameMenu({ invite: !me.guest && st.status !== "done" ? "quiz" : null,
      actions: [{ ic: "⏹", label: T("Stop"), danger: true, hidden: !isHost(st) || st.status === "done", confirm: T("Stop the quiz?"), onclick: () => act("abort") }],
      onLeave: () => { full(false); stop(); back(); } });
    const head = h("div.quiz-head", h("div.row.head-title", menu, h("h1", "🎯 ", C(st.title))), st.total ? h("span.chip", (st.idx + 1 > 0 ? st.idx + 1 : 0) + " / " + st.total) : null);
    // only the main action stays as a big button – everything else is in ☰
    const hostBar = isHost(st) && st.status !== "done" ? h("div.row.center.host-bar",
      h("button.btn", { onclick: () => act("next") }, st.status === "lobby" ? "▶ " + I18N.tr(T("Start")) : st.status === "question" ? I18N.tr(T("Show answer")) :
        st.idx + 1 >= st.total ? "🏁 " + I18N.tr(T("Finish")) : I18N.tr(T("Next question")) + " ➜")) : null;
    if (!st.joined && st.status !== "done") return show(head, h("section.card.center",
      h("p", T("Play along on this device?")), h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join"))), playersRow(st));
    if (st.status === "lobby") return show(head, h("section.card.center", h("h2", T("Waiting for the start …")),
      h("p.muted", T("Everybody joins on their own device.")), playersRow(st)), hostBar);
    if (st.status === "question") {
      const q = st.question, bar = h("div.quiz-time", h("i"));
      const end = Date.now() + q.remaining_ms;
      const upd = () => { const left = Math.max(0, end - Date.now()); bar.firstChild.style.width = (100 * left / (q.t * 1000)) + "%"; bar.dataset.s = Math.ceil(left / 1000); };
      upd(); tick = setInterval(upd, 200);
      const answered = st.my_choice != null;
      if (input.idx !== st.idx) input = { idx: st.idx };
      const progress = h("p.center.muted", answered ? T("Answer saved – wait for the others …") : "", " ", I18N.tr(T("{0} of {1} answered")).replace("{0}", st.answered.length).replace("{1}", st.players.length));
      if (q.kind === "estimate") {
        if (input.value == null) input.value = Math.round((q.min + q.max) / 2 / q.step) * q.step;
        const num = h("input.est-num", { type: "number", min: q.min, max: q.max, step: q.step, value: input.value, disabled: answered,
          oninput: e => { input.value = +e.target.value; slider.value = input.value; } });
        const slider = h("input.est-slider", { type: "range", min: q.min, max: q.max, step: q.step, value: input.value, disabled: answered,
          oninput: e => { input.value = +e.target.value; num.value = input.value; } });
        return show(head, h("section.card.quiz-q", CF(q.q, "h2"), questionImage(q.img), bar),
          h("section.card.est-box", h("div.row.center", num, q.unit ? C(q.unit, "span.est-unit") : null), slider,
            h("div.row.small.muted", h("span.grow", fmt(q.min, 2)), h("span", fmt(q.max, 2))),
            h("button.btn.big", { disabled: answered, onclick: () => act("answer", { idx: st.idx, value: input.value }) }, "✓ ", T("Answer"))),
          progress, hostBar);
      }
      if (q.kind === "pin") {
        const send = h("button.btn.big", { disabled: answered || input.lat == null, onclick: () => act("answer", { idx: st.idx, lat: input.lat, lon: input.lon }) }, "📌 ", T("Answer"));
        return show(head, h("section.card.quiz-q", CF(q.q, "h2"), bar),
          h("section.card", answered ? null : h("p.small.muted.center", T("Tap the map to set your pin.")),
            geoMap(q.map, { pick: answered ? null : (lat, lon) => { input.lat = lat; input.lon = lon; send.disabled = false; },
              pins: input.lat != null ? [{ lat: input.lat, lon: input.lon, me: true }] : [] }),
            h("div.row.center", send)),
          progress, hostBar);
      }
      return show(head, h("section.card.quiz-q", CF(q.q, "h2"), questionImage(q.img), bar),
        h("div.quiz-answers", ...q.a.map((a, i) => h("button.quiz-a" + (st.my_choice === i ? ".mine" : "") + (answered && st.my_choice !== i ? ".dim" : ""),
          { style: { "--c": QUIZ_COLORS[i] }, disabled: answered, onclick: () => act("answer", { idx: st.idx, choice: i }) },
          h("span.shape", QUIZ_SHAPES[i]), CF(a, onlyEmoji(a) ? "span.big-emoji" : "span")))),
        progress, hostBar);
    }
    if (st.status === "reveal" && st.solution) {
      const q = st.question, sol = st.solution, myG = (st.guesses || []).find(x => x.id === me.id);
      const msg = !myG ? T("Too late this time") : myG.points ? I18N.tr(T("Close! +{0} points")).replace("{0}", myG.points) : T("Others were closer this time");
      if (myG && myG.points === 1000) { try { Sound.play("right"); } catch {} }
      const missTxt = x => q.kind === "pin" ? Math.round(x.miss) + " km" : (x.miss === 0 ? "🎯" : "± " + fmt(x.miss, 2) + (sol.unit ? " " + sol.unit : ""));
      const list = h("ol.guess-list", ...(st.guesses || []).map(x => h("li" + (x.id === me.id ? ".me" : ""),
        C(x.name || "?", "strong.grow"), q.kind === "estimate" ? h("span", fmt(x.value, 2), sol.unit ? " " + sol.unit : "") : null,
        h("span.small.muted", missTxt(x)), x.points ? h("b", "+" + x.points) : null)));
      return show(head, h("section.card.quiz-q", CF(q.q, "h2"),
          q.kind === "estimate" ? h("div.est-solution", fmt(sol.value, 2), sol.unit ? " " + sol.unit : "") : h("div.est-solution", "📍 ", C(sol.label || "")),
          h("p.quiz-msg" + (myG && myG.points ? ".good" : ""), msg)),
        q.kind === "pin" ? h("section.card", geoMap(q.map, { target: sol, pins: (st.guesses || []).map(x => ({ lat: x.lat, lon: x.lon, name: x.name, me: x.id === me.id })) })) : null,
        h("section.card", list), scoreList(st, 5), hostBar);
    }
    if (st.status === "reveal") {
      const q = st.question, mine = st.my_choice;
      const msg = mine == null ? T("Too late this time") : mine === st.correct ? I18N.tr(T("Right! +{0} points")).replace("{0}", st.my_points) : T("Not this time");
      if (mine === st.correct) { try { Sound.play("right"); } catch {} }
      return show(head, h("section.card.quiz-q", CF(q.q, "h2"), questionImage(q.img), h("p.quiz-msg" + (mine === st.correct ? ".good" : ""), msg)),
        h("div.quiz-answers", ...q.a.map((a, i) => h("div.quiz-a" + (i === st.correct ? ".right" : ".dim"), { style: { "--c": QUIZ_COLORS[i] } },
          h("span.shape", QUIZ_SHAPES[i]), CF(a, onlyEmoji(a) ? "span.big-emoji" : "span"), h("b.count", String(st.counts[i]))))),
        scoreList(st, 5), hostBar);
    }
    // done: podium
    const top = st.players.filter(p => p.place <= 3);
    if (st.players.some(p => p.id === me.id && p.place === 1 && p.points > 0)) { confetti(); try { Sound.play("done"); } catch {} }
    show(head, h("section.card.center", h("h2", "🏁 ", T("Result")),
      h("div.podium", ...[1, 0, 2].map(i => top[i] ? h("div.pod.p" + top[i].place, avatarSvg(top[i].avatar, top[i].place === 1 ? 84 : 64),
        C(top[i].name, "strong"), h("span.small", top[i].points + " " + I18N.tr(T("points"))), h("div.step", top[i].place === 1 ? "🏆" : String(top[i].place))) : h("div")))),
      scoreList(st, 99), h("div.row.center.host-bar", h("button.btn", { onclick: back }, T("Back"))));
  }
  function playersRow(st) {
    return h("div.quiz-players", ...st.players.map(p => h("div.qp" + ((st.answered || []).includes(p.id) ? ".done" : ""), avatarSvg(p.avatar, 44), C(p.name, "span.small"))));
  }
  function scoreList(st, n) {
    return h("section.card", h("h3", T("Scores")), h("ol.scores", ...st.players.slice(0, n).map(p =>
      h("li" + (p.id === me.id ? ".me" : ""), h("b", p.place + "."), avatarSvg(p.avatar, 28), C(p.name, "span.grow"), h("span", String(p.points))))));
  }
  poll();
}

// ---------------------------------------------------------------- family council
// polls: a question with answers – one or several, anonymous or with names, optionally until a time
// ---------------------------------------------------------------- collapsed lists with the filter «active / closed»
// (council, polls, Wichteln): only the titles; tap one to open it. Opened ones stay open while the list refreshes.
const _openInst = new Set();
function instList(key, items, { closed, summary, body, labels, empty }) {
  let f = "active";
  try { f = localStorage.getItem("fq.inst." + key) || "active"; } catch {}
  const box = h("div.inst");
  const draw = () => {
    const act = items.filter(x => !closed(x)), done = items.filter(closed);
    const shown = f === "closed" ? done : act;
    box.replaceChildren(
      h("div.seg.inst-filter", ...[["active", (labels || [])[0] || T("Active"), act.length], ["closed", (labels || [])[1] || T("Closed"), done.length]].map(([k, n, c]) =>
        h("button" + (f === k ? ".on" : ""), { onclick: () => { f = k; try { localStorage.setItem("fq.inst." + key, k); } catch {} draw(); } }, n, " ", h("span.inst-n", String(c))))),
      shown.length ? h("div.inst-list", ...shown.map(x => {
        const id = key + ":" + x.id;
        return h("details.inst-item" + (f === "closed" ? ".closed" : ""), { open: _openInst.has(id), ontoggle: e => e.currentTarget.open ? _openInst.add(id) : _openInst.delete(id) },
          h("summary", ...summary(x)), h("div.inst-body", ...[].concat(body(x))));
      })) : h("p.small.muted.inst-empty", f === "closed" ? (empty || [])[1] || T("Nothing closed yet.") : (empty || [])[0] || T("Nothing active right now.")));
  };
  draw();
  return box;
}

async function pollsSection(me = S.profile) {
  const sec = h("section.card.polls", h("h2", "📊 ", T("Polls")));
  const draw = async () => {
    let polls = [];
    try { polls = await api("community/polls"); } catch (e) { return sec.append(h("p.bad", e.message)); }
    sec.replaceChildren(h("div.sec-head", h("h2", "📊 ", T("Polls")), h("div.head-actions", h("button.btn", { onclick: () => pollDialog(draw) }, "+ ", T("New poll")))),
      h("p.small.muted", T("Ask the family something – everybody answers on their own device and sees the result afterwards.")),
      instList("polls", polls, { closed: p => p.status === "closed",
        summary: p => [C(p.question, "strong.grow"), !p.my_votes.length && p.status !== "closed" ? h("span.chip.vote", T("answer")) : null,
          h("span.chip." + (p.status === "closed" ? "closed" : "vote"), p.status === "closed" ? T("closed") : T("open"))],
        body: card }));
  };
  const call2 = async (path, opts) => { try { await api(path, opts); draw(); } catch (e) { toast(e.message, "bad"); } };
  function card(p) {
    const manage = me.role === "parent" || p.created_by === me.id;
    const voted = p.my_votes.length > 0, closed = p.status === "closed";
    const sel = new Set(p.my_votes);
    const max = Math.max(1, ...p.options.map(o => o.votes || 0));
    const until = p.closes_at && !closed ? " · ⏰ " + new Date(p.closes_at).toLocaleString(I18N.locale, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "";
    const head = h("div.row", C(p.question, "h3.grow"), h("span.chip." + (closed ? "closed" : "vote"), closed ? T("closed") : T("open")));
    const meta = h("p.small.muted", I18N.tr(T("asked by {0}")).replace("{0}", p.author || "?"), " · ",
      p.multi ? T("several answers") : T("one answer"), p.anonymous ? " · 🕶️ " + I18N.tr(T("anonymous")) : "", until,
      " · ", I18N.tr(T("Votes: {0}")).replace("{0}", p.voters));
    const results = h("div.results", ...p.options.map(o => h("div.res",
      h("div.row.small", C(o.text, "span.grow"), sel.has(o.id) ? "✅ " : "", h("b", String(o.votes || 0))),
      h("div.res-bar", h("i", { style: { width: (100 * (o.votes || 0) / max) + "%" } })),
      o.names && o.names.length ? h("div.small.muted", C(o.names.join(", "))) : null)));
    const ballot = () => {
      const btns = p.options.map(o => h("button.vote" + (sel.has(o.id) ? ".mine" : ""), { onclick: e => {
        if (!p.multi) sel.clear();
        sel.has(o.id) ? sel.delete(o.id) : sel.add(o.id);
        e.currentTarget.parentNode.querySelectorAll(".vote").forEach((b, i) => { b.classList.toggle("mine", sel.has(p.options[i].id)); b.firstChild.textContent = sel.has(p.options[i].id) ? "✅ " : "⬜ "; });
        if (!p.multi) call2(`community/polls/${p.id}/vote`, { method: "POST", body: { options: [...sel] } });
      } }, h("span", sel.has(o.id) ? "✅ " : "⬜ "), C(o.text)));
      return h("div", h("div.vote-list", ...btns),
        p.multi ? h("button.btn.small", { onclick: () => call2(`community/polls/${p.id}/vote`, { method: "POST", body: { options: [...sel] } }) }, T("Send my answers")) : null);
    };
    return h("div.topic" + (closed ? ".closed" : ""), meta,
      !closed && !voted ? ballot() : null,
      voted || closed ? results : null,
      !closed && voted ? h("button.link.small", { onclick: e => { e.currentTarget.replaceWith(ballot()); } }, T("Change my answer")) : null,
      manage ? h("div.row", !closed ? h("button.btn.small.ghost", { onclick: () => call2(`community/polls/${p.id}/close`, { method: "POST" }) }, "🏁 ", T("Close the poll")) : null,
        h("button.btn.small.ghost", { onclick: () => confirm(I18N.tr(T("Remove this poll?"))) && call2(`community/polls/${p.id}`, { method: "DELETE" }) }, T("Remove"))) : null);
  }
  draw();
  return sec;
}

function pollDialog(done) {
  const q = h("input", { type: "text", maxlength: 200, placeholder: I18N.tr(T("e.g. Which pizza on Friday?")) });
  const list = h("div.poll-opts");
  const addOpt = (v = "") => { const i = h("input", { type: "text", maxlength: 120, value: v, placeholder: I18N.tr(T("Answer")) }); list.append(i); return i; };
  addOpt(); addOpt(); addOpt();
  const multi = h("input", { type: "checkbox" }), anon = h("input", { type: "checkbox" });
  const until = h("input", { type: "datetime-local" });
  const m = modal(h("div.form", h("h2", "📊 ", T("New poll")),
    h("label.field", T("Question"), q), h("div.field", h("b", T("Answers")), list,
      h("button.btn.small.ghost", { type: "button", onclick: () => addOpt().focus() }, "+ ", T("Add answer"))),
    h("label.check", multi, T("Several answers allowed")), h("label.check", anon, T("Anonymous (nobody sees who chose what)")),
    h("label.field", T("Closes at (optional)"), until),
    h("div.row", h("button.btn", { onclick: async () => {
      try {
        await api("community/polls", { method: "POST", body: { question: q.value, options: [...list.querySelectorAll("input")].map(i => i.value),
          multi: multi.checked, anonymous: anon.checked, closes_at: until.value || null } });
        m.close(); toast(T("Saved"), "good"); done();
      } catch (e) { toast(e.message, "bad"); }
    } }, T("Ask")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  q.focus();
}

const MAJ = { relative: T("Simple majority (most votes)"), absolute: T("Absolute majority (more than half)"), unanimous: T("Unanimous (everybody the same)") };

// a new topic of the family council: question, a few words, first ideas, the rule of the vote – collect first or vote now
function topicDialog(done) {
  const title = h("input", { type: "text", maxlength: 100, placeholder: I18N.tr(T("e.g. What do we do on Saturday?")) });
  const desc = h("textarea", { rows: 2, maxlength: 500, placeholder: I18N.tr(T("A few words more (optional)")) });
  const list = h("div.poll-opts");
  const addIdea = (v = "") => { const i = h("input", { type: "text", maxlength: 120, value: v, placeholder: I18N.tr(T("Your idea …")) }); list.append(i); return i; };
  addIdea(); addIdea();
  const maj = h("select", ...Object.entries(MAJ).map(([k, n]) => h("option", { value: k }, I18N.tr(n))));
  const both = h("input", { type: "checkbox" });
  let now = false;
  const flow = h("div.pin-kind");
  const drawFlow = () => flow.replaceChildren(...[[false, "💡 " + I18N.tr(T("Collect ideas first"))], [true, "🗳️ " + I18N.tr(T("Vote right away"))]].map(([v, n]) =>
    h("button.btn.small" + (now === v ? "" : ".ghost"), { type: "button", onclick: () => { now = v; drawFlow(); } }, n)));
  drawFlow();
  const m = modal(h("div.form", h("h2", "🗳️ ", T("New topic")),
    h("label.field", T("Question"), title), h("label.field", T("Description"), desc),
    h("div.field", h("b", T("First ideas")), list, h("button.btn.small.ghost", { type: "button", onclick: () => addIdea().focus() }, "+ ", T("Add idea")),
      h("p.small.muted", T("Everybody can add more ideas while the topic collects ideas."))),
    h("label.field", T("The vote needs"), maj),
    h("label.check", both, T("Parents and children: the winner needs at least one parent and one child")),
    h("div.field", h("b", T("How it goes on")), flow),
    h("div.row", h("button.btn.wichtel-draw", { onclick: async () => {
      if (!title.value.trim()) return title.focus();
      try {
        await api("community/council", { method: "POST", body: { title: title.value, description: desc.value,
          ideas: [...list.querySelectorAll("input")].map(i => i.value), majority: maj.value, both_sides: both.checked, vote_now: now } });
        m.close(); toast(T("Saved"), "good"); done();
      } catch (e) { toast(e.message, "bad"); }
    } }, "💾 ", T("Open the topic")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  title.focus();
}

// ---------------------------------------------------------------- Wichteln: who gives a present to whom – everybody sees only their own
async function wichtelnSection(me = S.profile) {
  const sec = h("section.card.wichteln");
  const draw = async () => {
    let d = { items: [], members: [] };
    try { d = await api("community/wichteln"); } catch (e) { return sec.replaceChildren(h("p.bad", e.message)); }
    sec.replaceChildren(h("div.sec-head", h("h2", "🎁 ", T("Wichteln")), h("div.head-actions", h("button.btn", { onclick: () => wichtelDialog(d.members, draw) }, "+ ", T("New Wichteln")))),
      h("p.small.muted", T("Who gives a present to whom is drawn at random – everybody sees only their own.")),
      instList("wichteln", d.items, { closed: w => !!w.due && w.due < new Date().toISOString().slice(0, 10),
        summary: w => [C(w.title, "strong.grow"), w.due ? h("span.small.muted", "📅 " + fmtDate(w.due)) : null, w.done ? h("span.chip.closed", "✓") : null],
        body: w => {
        const secret = h("div.wichtel-secret");
        const reveal = () => secret.replaceChildren(h("div.row", h("span", T("You give a present to:")), avatarSvg(w.mine.avatar, 44), C(w.mine.name, "strong.wichtel-name")),
          h("button.btn.ghost.small", { onclick: hide }, "🙈 ", T("Hide")));
        const hide = () => secret.replaceChildren(h("button.btn", { onclick: reveal }, "🎁 ", T("Show whom I give to")));
        if (w.mine) hide(); else secret.replaceChildren(h("p.small.muted", T("You are not taking part.")));
        const tick = w.mine ? h("label.check.wichtel-done", h("input", { type: "checkbox", checked: w.done, onchange: async e => {
          try { await api(`community/wichteln/${w.id}/done`, { method: "POST", body: { done: e.target.checked } }); }
          catch (err) { e.target.checked = !e.target.checked; toast(err.message, "bad"); } } }), T("Present ready")) : null;
        return h("div.topic", h("div.row", h("span.grow"),
            (w.created_by === me.id || me.role === "parent") ? h("button.icon-btn", { title: T("Delete"), onclick: async () => {
              if (!confirm(I18N.tr(T("Delete «{0}»?")).replace("{0}", w.title))) return;
              try { await api(`community/wichteln/${w.id}`, { method: "DELETE" }); draw(); } catch (e) { toast(e.message, "bad"); } } }, "🗑️") : null),
          h("p.small.muted", I18N.tr(T("With: {0}")).replace("{0}", w.people.map(p => p.name).join(", ")),
            w.rules.no_parent_pairs ? [" · ", I18N.tr(T("parents not among each other"))] : null, w.rules.no_kid_pairs ? [" · ", I18N.tr(T("children not among each other"))] : null),
          w.due ? h("p.small", "📅 ", new Date(w.due + "T12:00").toLocaleDateString(I18N.locale, { weekday: "short", day: "numeric", month: "long", year: "numeric" })) : null,
          secret, tick);
      } }));
  };
  draw();
  return sec;
}

function wichtelDialog(members, done) {
  const title = h("input", { type: "text", maxlength: 100, placeholder: I18N.tr(T("e.g. Christmas 2026")) });
  const due = h("input", { type: "date" });
  const chosen = new Set(members.map(m => m.id));
  const box = h("div.row.wrap");
  const drawPeople = () => box.replaceChildren(...members.map(m => h("label.check", h("input", { type: "checkbox", checked: chosen.has(m.id),
    onchange: e => { e.target.checked ? chosen.add(m.id) : chosen.delete(m.id); } }), C(m.name), m.role === "parent" ? h("span.small.muted", " 👪") : null)));
  drawPeople();
  const noParents = h("input", { type: "checkbox" }), noKids = h("input", { type: "checkbox" });
  const m = modal(h("div.form", h("h2", "🎁 ", T("New Wichteln")),
    h("label.field", T("Occasion"), title),
    h("label.field", T("Date (optional)"), due, h("span.hint", T("Everybody gets a to-do in the planner – without the name of whom they give to."))),
    h("div.wichtel-field", h("div.row", h("b.grow", T("Who takes part?")),
      h("button.btn.ghost.small", { type: "button", onclick: () => { members.forEach(x => chosen.add(x.id)); drawPeople(); } }, T("Whole family"))), box),
    h("div.wichtel-field", h("b", T("Rules")),
      h("label.check", noParents, T("Parents not among each other")),
      h("label.check", noKids, T("Children not among each other")),
      h("span.small.muted", T("Without a tick everybody can draw everybody (but never themselves)."))),
    h("div.row", h("button.btn.wichtel-draw", { onclick: async () => {
      if (!title.value.trim()) return title.focus();
      try {
        await api("community/wichteln", { method: "POST", body: { title: title.value, participants: [...chosen], no_parent_pairs: noParents.checked, no_kid_pairs: noKids.checked, due: due.value || null } });
        m.close(); toast(T("Drawn – everybody sees now whom they give to"), "good"); done();
      } catch (e) { toast(e.message, "bad"); }
    } }, "🎲 ", T("Draw")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  title.focus();
}

async function councilSection(me = S.profile) {
  const sec = h("section.card.council", h("h2", "🗳️ ", T("Family council")));
  const draw = async () => {
    let topics = [];
    try { topics = await api("community/council"); } catch (e) { return sec.append(h("p.bad", e.message)); }
    sec.replaceChildren(h("div.sec-head", h("h2", "🗳️ ", T("Family council")), h("div.head-actions", h("button.btn", { onclick: () => topicDialog(draw) }, "+ ", T("New topic")))),
      h("p.small.muted", T("Everybody can ask the family something, collect ideas and then vote – secretly, one vote each.")),
      instList("council", topics, { closed: t => t.status === "closed",
        summary: t => { const und = t.status === "closed" && t.result && t.result.decided === false;
          return [C(t.title, "strong.grow"), t.status === "vote" && !t.my_vote ? h("span.chip.vote", T("vote")) : null,
            h("span.chip." + (und ? "vote" : t.status), und ? T("No decision") : { collect: T("collecting ideas"), vote: T("vote running"), closed: T("decided") }[t.status])]; },
        body: topicCard }));
  };
  const call2 = async (path, opts) => { try { await api(path, opts); draw(); } catch (e) { toast(e.message, "bad"); } };
  function voteDialog(t) {
    const sel = h("select.maj-sel", ...Object.entries(MAJ).map(([k, n]) => h("option", { value: k, selected: k === (t.majority || "relative") }, n)));
    const both = h("input", { type: "checkbox", checked: !!t.both_sides });
    const m = modal(h("div.form", h("h2", "🗳️ ", T("Start the vote")), C(t.title, "p"),
      h("label.field", T("The vote needs"), sel), h("label.check", both, T("Parents and children: the winner needs at least one parent and one child")),
      h("div.row", h("button.btn.good", { onclick: async () => { m.close(); await call2(`community/council/${t.id}/start-vote`, { method: "POST", body: { majority: sel.value, both_sides: both.checked } }); } }, "🗳️ ", T("Start the vote")),
        h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  }
  function topicCard(t) {
    const manage = me.role === "parent" || t.created_by === me.id;
    const maj = t.majority || "relative";
    const open = t.status === "closed" && t.result && t.result.decided === false;
    const chipTxt = open ? T("No decision") : { collect: T("collecting ideas"), vote: T("vote running"), closed: T("decided") }[t.status];
    const headRow = null;      // the title and the state are in the line of the list
    const by = [t.description ? C(t.description, "p") : null, h("p.small.muted", I18N.tr(T("asked by {0}")).replace("{0}", t.author || "?"))];
    if (t.status === "collect") {
      const inp = h("input", { type: "text", maxlength: 120, placeholder: I18N.tr(T("Your idea …")) });
      return h("div.topic", headRow, by,
        h("ul.list", ...t.proposals.map(c => h("li.row", C(c.text, "span.grow"), C(c.author || "", "span.small.muted"),
          c.profile_id === me.id || me.role === "parent" ? h("button.icon-btn", { title: T("Remove"), onclick: () => call2(`community/council/proposals/${c.id}`, { method: "DELETE" }) }, "✕") : null))),
        h("div.row", inp, h("button.btn.small", { onclick: () => inp.value.trim() && call2(`community/council/${t.id}/proposals`, { method: "POST", body: { text: inp.value } }) }, "+ ", T("Add idea"))),
        manage ? h("div.row.wrap",
          h("button.btn.small.good", { disabled: t.proposals.length < 2, title: t.proposals.length < 2 ? T("At least two ideas") : "", onclick: () => voteDialog(t) }, "🗳️ ", T("Start the vote")),
          h("button.btn.small.ghost", { onclick: () => confirm(I18N.tr(T("Remove this topic?"))) && call2(`community/council/${t.id}`, { method: "DELETE" }) }, T("Remove"))) : null);
    }
    const bothTxt = t.both_sides ? " · 👨‍👩‍👧 " + I18N.tr(T("parents and children")) : "";
    if (t.status === "vote") return h("div.topic", headRow, by, h("p.small", "⚖️ ", MAJ[maj], bothTxt),
      h("p.small", t.my_vote ? T("You voted – you can still change your vote.") : T("Tap your favourite:")),
      h("div.vote-list", ...t.proposals.map(c => h("button.vote" + (t.my_vote === c.id ? ".mine" : ""),
        { onclick: () => call2(`community/council/${t.id}/vote`, { method: "POST", body: { proposal_id: c.id } }) }, t.my_vote === c.id ? "✅ " : "⬜ ", C(c.text)))),
      h("p.small.muted", I18N.tr(T("Voted so far: {0}")).replace("{0}", t.voters.join(", ") || "–")),
      manage ? h("button.btn.small", { onclick: () => call2(`community/council/${t.id}/close`, { method: "POST" }) }, "🏁 ", T("End the vote")) : null);
    const max = Math.max(1, ...t.proposals.map(c => c.votes || 0));
    const undecided = t.result && t.result.decided === false;
    return h("div.topic.closed", headRow,
      undecided
        ? h("div", h("p", "❌ ", h("strong", T("No decision")), " – ", t.result.sides_ok === false ? T("the proposal did not get a parent's and a child's vote.") : maj === "unanimous" ? T("not everybody chose the same.") : maj === "absolute" ? T("no proposal got more than half of the votes.") : T("No votes")),
            manage ? h("div.row.wrap",
              h("button.btn.small", { onclick: () => call2(`community/council/${t.id}/revote`, { method: "POST", body: { runoff: false } }) }, "🔁 ", T("Vote again")),
              maj !== "unanimous" && t.proposals.length > 2 ? h("button.btn.small.ghost", { onclick: () => call2(`community/council/${t.id}/revote`, { method: "POST", body: { runoff: true } }) }, "⚔️ ", T("Run-off between the two best")) : null) : null)
        : h("p", "🏆 ", t.result && t.result.winners.length ? C(t.result.winners.join(" / "), "strong") : T("No votes"), t.result && t.result.tie ? h("span.small.muted", " (" + I18N.tr(T("tie")) + ")") : null),
      h("p.small.muted", "⚖️ ", MAJ[maj], bothTxt, t.result ? " · " + I18N.tr(T("Votes: {0}")).replace("{0}", t.result.voters) : ""),
      h("div.results", ...t.proposals.slice().sort((a, b) => (b.votes || 0) - (a.votes || 0)).map(c => h("div.res",
        h("div.row.small", C(c.text, "span.grow"), h("b", String(c.votes || 0))), h("div.res-bar", h("i", { style: { width: (100 * (c.votes || 0) / max) + "%" } }))))));
  }
  draw();
  return sec;
}

// ---------------------------------------------------------------- personal history
function historyText(e) {
  const d = e.data;
  if (e.kind === "quiz") return ["🎯", I18N.tr(T("Family quiz «{0}»: place {1} of {2} · {3} points")).replace("{0}", d.quiz).replace("{1}", d.place).replace("{2}", d.of).replace("{3}", d.points), d.won ? "🏆" : ""];
  if (e.kind === "council") return ["🗳️", I18N.tr(T("Family council «{0}»: {1}")).replace("{0}", d.topic).replace("{1}", d.decided === false ? I18N.tr(T("No decision")) : (d.winners || []).join(" / ") || "–"), d.mine_won ? I18N.tr(T("your idea!")) : ""];
  if (e.kind === "bingo") return ["🎱", I18N.tr(T("Bingo with {0} players: {1} won after {2} balls")).replace("{0}", d.players).replace("{1}", d.winner).replace("{2}", d.balls), d.won ? "🏆" : ""];
  if (e.kind === "song") return ["🎵", I18N.tr(T("Guess the song: place {0} of {1} · {2} points")).replace("{0}", d.place).replace("{1}", d.players).replace("{2}", d.points), d.place === 1 ? "🏆" : ""];
  if (e.kind === "domino") return ["🁫", I18N.tr(T("Domino: {0} to {1} points")).replace("{0}", d.points).replace("{1}", d.best) + (d.pollona ? " · Pollona" : ""), d.won ? "🏆" : ""];
  if (e.kind === "paarjagd") return ["🧠", I18N.tr(T("Paarjagd: place {0} of {1} · {2} pairs")).replace("{0}", d.place).replace("{1}", d.players).replace("{2}", d.pairs)
    + (d.coins ? " · +" + d.coins + " 🪙" : ""), d.place === 1 ? "🏆" : ""];
  if (e.kind === "werbinich") return ["🎭", (d.found
    ? I18N.tr(T("Wer bin ich?: place {0} of {1} · I was {2}")).replace("{0}", d.place).replace("{1}", d.players).replace("{2}", d.char)
    : I18N.tr(T("Wer bin ich?: I was {0} – not found")).replace("{0}", d.char)) + (d.coins ? " · +" + d.coins + " 🪙" : ""), d.place === 1 ? "🏆" : ""];
  if (e.kind === "kartenlauf") return ["🏁", I18N.tr(T("Kartenlauf: place {0} of {1} · {2} marbles home")).replace("{0}", d.place).replace("{1}", d.players).replace("{2}", d.home)
    + (d.teams ? " · " + I18N.tr(T("in a team")) : "") + (d.coins ? " · +" + d.coins + " 🪙" : ""), d.place === 1 ? "🏆" : ""];
  if (e.kind === "stadtland") return ["🏙️", I18N.tr(T("Stadt-Land-Fluss: place {0} of {1} · {2} points")).replace("{0}", d.place).replace("{1}", d.players).replace("{2}", d.points)
    + (d.coins ? " · +" + d.coins + " 🪙" : ""), d.place === 1 ? "🏆" : ""];
  if (e.kind === "zeichnen") return ["🎨", I18N.tr(T("Zeichnen & Raten: place {0} of {1} · {2} points")).replace("{0}", d.place).replace("{1}", d.players).replace("{2}", d.points)
    + (d.coins ? " · +" + d.coins + " 🪙" : ""), d.place === 1 ? "🏆" : ""];
  if (e.kind === "wuerfel") return ["🎲", I18N.tr(T("Fünf Würfel: place {0} of {1} · {2} points")).replace("{0}", d.place).replace("{1}", d.players).replace("{2}", d.points)
    + (d.coins ? " · +" + d.coins + " 🪙" : ""), d.place === 1 ? "🏆" : ""];
  if (e.kind === "heimwaerts") return ["🏠", I18N.tr(T("Heimwärts: place {0} of {1} · {2} pieces home")).replace("{0}", d.place).replace("{1}", d.players).replace("{2}", d.home)
    + (d.coins ? " · +" + d.coins + " 🪙" : ""), d.place === 1 ? "🏆" : ""];
  if (e.kind === "jump") return ["🦘", (d.players > 1
    ? I18N.tr(T("Jump: place {0} of {1} · {2} m")).replace("{0}", d.place).replace("{1}", d.players).replace("{2}", d.score)
    : I18N.tr(T("Jump alone: {0} m")).replace("{0}", d.score)) + (d.record ? " · 🎉 " + I18N.tr(T("New personal best!")) : "")
    + (d.coins ? " · +" + d.coins + " 🪙" : ""), d.place === 1 && d.players > 1 ? "🏆" : ""];
  if (e.kind === "klatsch") return ["👏", (d.players > 1
    ? I18N.tr(T("Klatsch den Beat: place {0} of {1} · {2} points")).replace("{0}", d.place).replace("{1}", d.players).replace("{2}", d.score)
    : I18N.tr(T("Klatsch den Beat alone: {0} points")).replace("{0}", d.score)) + " · " + I18N.tr(T("{0} % on the beat")).replace("{0}", d.acc || 0)
    + (d.record ? " · 🎉 " + I18N.tr(T("New personal best!")) : "") + (d.coins ? " · +" + d.coins + " 🪙" : ""), d.place === 1 && d.players > 1 ? "🏆" : ""];
  if (e.kind === "verboten") return ["🚫", I18N.tr(T("Verbotene Wörter: place {0} of {1} · {2} points")).replace("{0}", d.place).replace("{1}", d.players).replace("{2}", d.points)
    + (d.teams ? " · " + I18N.tr(T("in a team")) : "") + (d.coins ? " · +" + d.coins + " 🪙" : ""), d.place === 1 ? "🏆" : ""];
  if (e.kind === "jass") return ["♣️", I18N.tr(d.place === 1 ? T("Jass won {0} : {1}") : T("Jass lost {0} : {1}")).replace("{0}", d.points).replace("{1}", d.other)
    + (d.partner ? " · " + I18N.tr(T("with {0}")).replace("{0}", d.partner) : "") + (d.coins ? " · +" + d.coins + " 🪙" : ""), d.place === 1 ? "🏆" : ""];
  if (e.kind === "werwolf") return ["🐺", I18N.tr(d.won ? T("Werwölfe: won as {0}") : T("Werwölfe: lost as {0}")).replace("{0}", I18N.tr(werwolfRoleName(d.role)))
    + (d.coins ? " · +" + d.coins + " 🪙" : ""), d.won ? "🏆" : ""];
  if (e.kind === "schach") return ["♟️", (d.mode === "local"
    ? I18N.tr(d.result === "draw" ? T("Chess on one device: draw") : d.result === "white" ? T("Chess on one device: White won") : T("Chess on one device: Black won"))
    : I18N.tr(d.result === "win" ? T("Chess: won against {0}") : d.result === "loss" ? T("Chess: lost against {0}") : T("Chess: draw against {0}")).replace("{0}", d.opp || "?"))
    + " · " + I18N.tr(chReason(d.reason)) + (d.coins ? " · +" + d.coins + " 🪙" : ""), d.result === "win" ? "🏆" : ""];
  if (e.kind === "dorfmarkt") return ["🏘️", I18N.tr(T("Dorfmarkt: place {0} of {1} · {2} Taler")).replace("{0}", d.place).replace("{1}", d.players).replace("{2}", Number(d.worth || 0).toLocaleString("de-CH"))
    + (d.coins ? " · +" + d.coins + " 🪙" : ""), d.place === 1 ? "🏆" : ""];
  return ["•", e.kind, ""];
}

async function historySection(profileId, title = T("My history")) {
  const sec = h("section.card", h("h2", "📜 ", title));
  try {
    const items = await api("community/history" + (profileId ? "?profile_id=" + profileId : ""));
    sec.append(items.length ? h("ul.list.history", ...items.map(e => { const [ic, txt, extra] = historyText(e);
      return h("li.row", h("span.big-ic", ic), h("span.grow", h("span", { translate: "no" }, txt), extra ? h("b", " ", extra) : null),
        h("span.small.muted", new Date(e.at.replace(" ", "T")).toLocaleDateString(I18N.locale, { day: "numeric", month: "short" }))); }))
      : h("p.muted", T("Family quiz wins and council decisions will show up here.")));
  } catch (e) { sec.append(h("p.bad", e.message)); }
  return sec;
}

async function quizCard() {
  const c = S.me && S.me.community;
  const q = c && c.quiz;
  return h("section.card.quiz-card", h("h2", "🎯 ", T("Family quiz")),
    q && q.status !== "done" ? [h("p", C("«" + q.title + "»"), " ", T("is running – join in!")), h("button.btn.big", { onclick: () => go("quiz") }, "🙋 ", q.joined ? T("Back to the quiz") : T("Join"))]
      : [h("p.muted", T("Play a quiz together – everybody on their own device. Make your own quiz or take one of the templates.")),
         h("button.btn", { onclick: () => go("quizzes") }, "🎯 ", T("Quizzes"))]);
}

async function quizzesView() {
  const box = h("div");
  const actions = h("div.head-actions");
  screen("games", { back: () => go("games") }, h("section.card", h("div.sec-head", h("h2", "🎯 ", T("Family quiz")), actions), box));
  quizzesPanel(box, S.profile, () => go("quiz"), { actions });
}

// list of quizzes with start / edit / delete, templates, editor – for profile `me`
// `actions`: the head row of the section the «+ New quiz» button goes into
async function quizzesPanel(box, me, onStarted, { actions } = {}) {
  let quizzes = [], templates = [];
  try { [quizzes, templates] = await Promise.all([api("community/quizzes"), api("community/templates")]); }
  catch (e) { return box.replaceChildren(h("p.bad", e.message)); }
  const mine = q => me.role === "parent" || q.created_by === me.id;
  const start = async q => {
    const count = h("select", ...[5, 10, 15, 0].filter(n => !n || n < q.questions.length).map(n => h("option", { value: n }, n ? String(n) : I18N.tr(T("all")) + " (" + q.questions.length + ")")));
    const m = modal(h("div.form", h("h2", "▶ ", C(q.title)), h("label.field", T("How many questions?"), count),
      h("p.small.muted", T("Questions and answers come in a mixed order. You lead the game: you show the next question.")),
      h("div.row", h("button.btn.big", { onclick: async () => {
        try { await api("community/quiz/start", { method: "POST", body: { quiz_id: q.id, count: +count.value || null } }); m.close(); onStarted(); }
        catch (e) { toast(e.message, "bad"); }
      } }, "▶ ", T("Start")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  };
  const reload = () => quizzesPanel(box, me, onStarted, { actions });
  let region = "all";
  try { region = localStorage.getItem("fq.tplRegion") || "all"; } catch {}
  // «New quiz»: an own quiz or one of the templates – the templates only show up here, the list stays short
  const newQuiz = () => {
    const tplGrid = h("div.tpl-grid");
    let m;
    const drawTemplates = () => tplGrid.replaceChildren(...templates.filter(t => region === "all" || t.region === region).map(t => h("button.card.tpl", { onclick: async () => {
        try { await api("community/quizzes/from-template", { method: "POST", body: { template: t.id } }); toast(T("Added to our quizzes"), "good"); m.close(); reload(); }
        catch (e) { toast(e.message, "bad"); }
      } }, h("span.big-ic", t.icon), C(t.title, "strong"), h("span.small.muted", t.questions + " " + I18N.tr(T("questions"))), C(t.example, "span.small.tpl-ex"))));
    const regionSel = h("select", { style: { width: "auto", minWidth: "160px" }, onchange: e => { region = e.target.value; try { localStorage.setItem("fq.tplRegion", region); } catch {} drawTemplates(); } },
      ...Object.entries(TPL_REGIONS).filter(([k]) => k === "all" || templates.some(t => t.region === k))
        .map(([k, n]) => h("option", { value: k, selected: k === region }, I18N.tr(n))));
    // … or made by an AI: the template for the AI, then upload its answer (a JSON file)
    const file = h("input", { type: "file", accept: ".json,.txt,.md,application/json,text/plain", hidden: true, onchange: async () => {
      const f = file.files[0]; if (!f) return;
      try {
        const r = await api("community/quizzes/import", { method: "POST", body: { text: await f.text() } });
        toast(I18N.tr(T("{0} quizzes imported")).replace("{0}", r.ids.length), "good"); m.close(); reload();
      } catch (e) { toast(e.message, "bad"); }
      file.value = "";
    } });
    // … or made by an AI: download the template for the AI, then import its answer (a JSON file)
    const aiBox = h("div.ai-box",
      h("div.row.wrap",
        h("button.btn.small", { onclick: () => file.click() }, "⬆️ ", T("Import")),
        h("a.btn.small.ghost", { style: { textDecoration: "none" }, href: "api/ai-template/quiz", download: "family-quest-quiz-template.json" }, "⬇️ ", T("Download template")),
        quizzes.length ? h("button.btn.small.ghost", { onclick: () => downloadApi("community/quizzes/export", "family-quest-quizzes.json") }, "⬇️ ", T("Export all")) : null,
        file),
      h("p.small.muted", T("Made with your AI: the template and every export are JSON files that explain themselves to an AI. Give one to ChatGPT, Claude, Gemini … and say what the quiz should be about (or what to change) – all question types work: answers with text or flags, pictures (flags, emoji, own SVG drawings, cantons), estimation and map questions, mixed. Import its answer.")));
    m = modal(h("div.form", h("h2", "🎯 ", T("New quiz")),
      h("button.btn.big", { onclick: () => { m.close(); quizEditor(null, reload); } }, "✏️ ", T("Make an own quiz")),
      aiBox,
      h("div.row.wrap", h("h3.grow", T("… or take a template")), h("label.row.small", { style: { flexWrap: "nowrap" } }, T("Show:"), regionSel)),
      tplGrid, h("div.row", h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))), { wide: true });
    drawTemplates();
  };
  const newBtn = h("button.btn", { onclick: newQuiz }, "+ ", T("New quiz"));
  if (actions) actions.replaceChildren(...[...actions.children].filter(x => !x.classList.contains("new-quiz")), Object.assign(newBtn, { className: newBtn.className + " new-quiz" }));
  const del = async q => {
    if (!confirm(I18N.tr(T("Delete this quiz?")))) return;
    try { await api(`community/quizzes/${q.id}`, { method: "DELETE" }); reload(); } catch (e) { toast(e.message, "bad"); }
  };
  box.replaceChildren(...[
    actions ? null : h("div.sec-head", h("span.grow"), h("div.head-actions", newBtn)),
    h("p.small.muted", T("Play a quiz together – everybody on their own device. Make your own quiz or take one of the templates.")),
    instList("quizzes", quizzes, { closed: q => q.games > 0,
      labels: [T("Not played yet"), T("Played")], empty: [T("All quizzes have been played – make a new one!"), T("No quiz played yet.")],
      summary: q => [C(q.title, "strong.grow"), h("span.chip", q.questions.length + " " + I18N.tr(T("questions")))],
      body: q => h("div.topic",
        h("p.small.muted", I18N.tr(T("by {0}")).replace("{0}", q.author || "?"),
          q.games ? " · " + I18N.tr(T("played {0}×")).replace("{0}", q.games) : "",
          q.last_played ? " · " + I18N.tr(T("last {0}")).replace("{0}", fmtDate(q.last_played)) : "",
          q.last_winner ? [" · 🏆 ", C(q.last_winner.name), " (" + fmt(q.last_winner.points) + ")"] : null),
        h("div.row.wrap", h("button.btn", { onclick: () => start(q) }, "▶ ", T("Play")),
          mine(q) ? h("button.btn.ghost", { onclick: () => quizEditor(q, reload) }, "✏️ ", T("Edit")) : null,
          mine(q) ? h("button.btn.ghost", { onclick: () => del(q) }, "🗑️ ", T("Delete")) : null,
          h("button.btn.ghost", { onclick: () => downloadApi(`community/quizzes/${q.id}/export`, `family-quest-quiz-${q.id}.json`) }, "⬇️ ", T("Export")))) })].filter(Boolean));
}

// the template collections by region – the choice is remembered on this device
const TPL_REGIONS = { all: T("All"), general: T("General"), ch: T("Switzerland"), de: T("Germany"), at: T("Austria"), nl: T("Netherlands"), fr: T("France") };

function quizEditor(q, done) {
  const quiz = q ? JSON.parse(JSON.stringify(q)) : { title: "", questions: [{ q: "", a: ["", ""], c: 0, t: 20 }] };
  const title = h("input", { type: "text", maxlength: 80, value: quiz.title, placeholder: I18N.tr(T("e.g. Our holidays")) });
  const list = h("div.qe-list");
  const KINDS = { choice: T("Multiple choice"), estimate: T("Estimate a number"), pin: T("Place on a map") };
  const setKind = (i, k) => {       // keep text and time, start the new type empty
    const x = quiz.questions[i], base = { q: x.q, t: x.t || 20 };
    quiz.questions[i] = k === "estimate" ? { ...base, kind: k, answer: "", min: 0, max: 100, unit: "", t: Math.max(base.t, 30) }
      : k === "pin" ? { ...base, kind: k, map: "ch", label: "", t: Math.max(base.t, 30) } : { ...base, a: ["", ""], c: 0 };
    draw();
  };
  const num = (x, key, ph) => h("label.field", ph, h("input", { type: "number", value: x[key] ?? "", step: "any", oninput: e => { x[key] = e.target.value === "" ? null : +e.target.value; } }));
  const body = (x, i) => {
    if (x.kind === "estimate") return [h("div.grid2", num(x, "answer", T("Right answer")),
        h("label.field", T("Unit"), h("input", { type: "text", maxlength: 20, value: x.unit || "", placeholder: "m, km, kg …", oninput: e => { x.unit = e.target.value; } })),
        num(x, "min", T("Minimum")), num(x, "max", T("Maximum"))),
      h("p.small.muted", T("Everybody picks a number between minimum and maximum – the closest wins."))];
    if (x.kind === "pin") {
      const mapBox = h("div");
      const drawMap = () => mapBox.replaceChildren(geoMap(x.map, { pick: (lat, lon) => { x.lat = +lat.toFixed(4); x.lon = +lon.toFixed(4); },
        pins: x.lat != null ? [{ lat: x.lat, lon: x.lon, me: true }] : [] }));
      drawMap();
      return [h("div.grid2",
          h("label.field", T("Map"), h("select", { onchange: e => { x.map = e.target.value; delete x.lat; delete x.lon; drawMap(); } },
            h("option", { value: "ch", selected: x.map === "ch" }, T("Switzerland")), h("option", { value: "europe", selected: x.map === "europe" }, T("Europe")))),
          h("label.field", T("Name of the place"), h("input", { type: "text", maxlength: 60, value: x.label || "", placeholder: "Bern", oninput: e => { x.label = e.target.value; } }))),
        h("p.small.muted", T("Tap the map where the right place is. The closest pin wins.")), mapBox];
    }
    return [...x.a.map((a, j) => h("div.row.qe-a", { style: { "--c": QUIZ_COLORS[j] } },
        h("label.check", h("input", { type: "radio", name: "c" + i, checked: x.c === j, onchange: () => { x.c = j; } }), h("span.shape", QUIZ_SHAPES[j])),
        h("input.grow", { type: "text", maxlength: 120, value: a, placeholder: j === x.c ? I18N.tr(T("Right answer")) : I18N.tr(T("Answer")), oninput: e => { x.a[j] = e.target.value; } }),
        x.a.length > 2 ? h("button.icon-btn", { onclick: () => { x.a.splice(j, 1); if (x.c >= x.a.length) x.c = 0; draw(); } }, "−") : null)),
      x.a.length < 4 ? h("button.btn.small.ghost", { onclick: () => { x.a.push(""); draw(); } }, "+ ", T("Answer")) : null,
      h("p.small.muted", T("Tick the right answer."))];
  };
  const draw = () => list.replaceChildren(...quiz.questions.map((x, i) => h("div.card.qe",
    h("div.row", h("b", (i + 1) + "."), h("input.grow", { type: "text", maxlength: 300, value: x.q, placeholder: I18N.tr(T("Question")), oninput: e => { x.q = e.target.value; } }),
      h("select", { onchange: e => { x.t = +e.target.value; } }, ...[...new Set([10, 20, 30, 60, x.t || 20])].sort((u, v) => u - v).map(n => h("option", { value: n, selected: (x.t || 20) === n }, n + " s"))),
      h("button.icon-btn", { title: T("Delete"), onclick: () => { quiz.questions.splice(i, 1); draw(); } }, "✕")),
    h("select.qe-kind", { onchange: e => setKind(i, e.target.value) },
      ...Object.entries(KINDS).map(([k, n]) => h("option", { value: k, selected: (x.kind || "choice") === k }, I18N.tr(n)))),
    ...body(x, i))));
  draw();
  const m = modal(h("div.form", h("h2", q ? T("Edit quiz") : T("New quiz")), h("label.field", T("Title"), title), list,
    h("button.btn.ghost", { onclick: () => { quiz.questions.push({ q: "", a: ["", ""], c: 0, t: 20 }); draw(); } }, "+ ", T("Question")),
    h("div.row.sticky-actions", h("button.btn", { onclick: async () => {
      quiz.title = title.value;
      try { await api(q ? `community/quizzes/${q.id}` : "community/quizzes", { method: q ? "PUT" : "POST", body: { title: quiz.title, questions: quiz.questions } }); m.close(); done(); }
      catch (e) { toast(e.message, "bad"); }
    } }, "💾 ", T("Save")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))), { wide: true });
}

// ---------------------------------------------------------------- bingo
const BINGO_COLORS = ["#e03131", "#f08c00", "#fcc419", "#2f9e44", "#1971c2"];      // B I N G O
const bingoLetter = n => "BINGO"[Math.floor((n - 1) / 15)] || "";
const bingoColor = n => BINGO_COLORS[Math.floor((n - 1) / 15)] || "#868e96";
const SPIN_MS = 3000;                 // the carousel spins, then shows the ball for the rest of the interval (≥ 5 s)

function bingoBall(n, big) {
  return h("span.bball" + (big ? ".big" : ""), { style: { "--b": bingoColor(n) } }, h("small", bingoLetter(n)), h("b", String(n)));
}

const BINGO_WINS = { line: T("one line (row, column or diagonal)"), two_lines: T("two lines"), full: T("the full card") };

function bingoRules(r) {
  r = r || {};
  return h("div.rules", h("h2", "📜 ", T("Rules")), h("ul",
    h("li", T("Everybody gets a card with 25 fields: B 1–15, I 16–30, N 31–45, G 46–60, O 61–75 – the star in the middle is free.")),
    h("li", I18N.tr(T("A new ball comes every {0} seconds. Mark the number yourself if it is on your card.")).replace("{0}", r.interval || 8)),
    h("li", I18N.tr(T("To win you need: {0}.")).replace("{0}", I18N.tr(BINGO_WINS[r.win] || BINGO_WINS.line))),
    h("li", T("Then press «BINGO!». The app checks it – a false «Bingo!» blocks the button for 10 seconds."))));
}

// who starts sets the rules; the rules used last are the default
async function bingoStartDialog(onStarted) {
  let r = { interval: 8, win: "line" };
  try { r = await api("community/bingo/rules"); } catch {}
  const speed = h("select", h("option", { value: 8, selected: r.interval === 8 }, T("normal") + " (8 s)"), h("option", { value: 12, selected: r.interval === 12 }, T("slow") + " (12 s)"));
  const win = h("select", ...Object.entries(BINGO_WINS).map(([k, n]) => h("option", { value: k, selected: r.win === k }, I18N.tr(n))));
  const m = modal(h("div.form", h("h2", "🎱 ", T("Start bingo")),
    h("div.grid2", h("label.field", T("Speed"), speed), h("label.field", T("To win"), win)),
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      try { await api("community/bingo/start", { method: "POST", body: { interval: +speed.value, win: win.value } }); m.close(); onStarted(); }
      catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", T("Start")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
}

async function bingoView() {
  const box = h("div.bingo-live");
  screen("games", box);
  bingoLive(box, S.profile, () => go("games"));
}

// the live bingo in `box` for profile `me` (learning app and parent area)
function bingoLive(box, me, back) {
  let st = null, timer = null, alive = true, anim = null, lastSig = "";
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => { alive = false; clearTimeout(timer); clearInterval(anim); box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open"); };
  window.addEventListener("hashchange", stop, { once: true });
  const act = async (path, body) => {
    try { const r = await api("community/bingo/" + path, { method: "POST", body }); if (r && r.state !== undefined) { st = r.state; draw(true); return r; } st = r; draw(true); return r; }
    catch (e) { toast(e.message, "bad"); }
  };
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try { st = await api("community/bingo"); draw(); } catch {}
    timer = setTimeout(poll, 1000);
  }
  // the carousel: spins for SPIN_MS after a new ball, then stops and shows it
  const carousel = h("div.bingo-carousel", h("div.ring", ...Array.from({ length: 10 }, (_, i) =>
    h("i", { style: { "--a": (i * 36) + "deg", "--b": BINGO_COLORS[i % 5] } }))), h("div.center"));
  let cycleStart = 0, shown = null;
  const tickCarousel = () => {
    if (!st || st.status !== "running" || !st.current) { carousel.classList.remove("spin"); return; }
    const t = Date.now() - cycleStart, spinning = !st.paused && t < SPIN_MS;
    carousel.classList.toggle("spin", spinning);
    const center = carousel.querySelector(".center");
    if (spinning) { if (shown !== null) { center.replaceChildren(); shown = null; } }
    else if (shown !== st.current) { center.replaceChildren(bingoBall(st.current, true)); shown = st.current; try { Sound.play("tap"); } catch {} }
  };
  function draw(force) {
    if (!alive || !box.isConnected) return;                            // the game was left meanwhile: a late answer
    if (st && !Array.isArray(st.players)) st = null;                 // not a game state (e.g. after «end»): no game
    const sig = JSON.stringify(st && [st.status, st.count, st.paused, st.marks, Math.ceil((st.blocked_ms || 0) / 1000), st.players.length, st.winner && st.winner.id]);
    if (st && st.status === "running") cycleStart = Date.now() - st.phase_ms;
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    if (!st) return show(h("section.card.center", h("div.big-ic", "🎱"), h("h2", T("No bingo right now")),
      h("p.muted", T("Start a game – everybody plays on their own device.")), h("button.btn", { onclick: back }, T("Back"))));
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    // ☰: rules, guests (everybody of the family), pause / end for whoever leads, language
    const lead = isHost() && st.status !== "done";
    const menu = gameMenu({ rules: () => bingoRules(st.rules),
      invite: !me.guest && st.status !== "done" ? "bingo" : null,
      actions: [
        { ic: st.paused ? "▶" : "⏸", label: st.paused ? T("Go on") : T("Pause"), hidden: !lead || st.status === "lobby", onclick: () => act("pause", { on: !st.paused }) },
        { ic: "⏹", label: T("End the game"), danger: true, hidden: !lead, confirm: T("End the game?"), onclick: () => act("end").then(() => { stop(); back(); }) }],
      onLeave: running ? () => { stop(); back(); } : null });
    const head = h("div.quiz-head", h("div.row.head-title", menu, h("h1", "🎱 Bingo")), h("div.row",
      st.count ? h("span.chip", st.count + " / 75") : null));
    const players = h("div.quiz-players", ...st.players.map(p => h("div.qp.done", avatarSvg(p.avatar, 40), C(p.name, "span.small"))));
    // only the main action stays as a big button (start; «go on» while paused) – everything else is in ☰
    const host = lead && (st.status === "lobby" || st.paused) ? h("div.row.center.host-bar",
      st.status === "lobby" ? h("button.btn", { onclick: () => act("begin") }, "▶ ", T("Start"))
        : h("button.btn", { onclick: () => act("pause", { on: false }) }, "▶ ", T("Go on"))) : null;
    if (st.status === "done") {
      const won = st.winner && st.winner.id === me.id;
      if (won) { confetti(); try { Sound.play("done"); } catch {} }
      return show(head, h("section.card.center", h("h2", "🎉 BINGO!"),
        st.winner ? [avatarSvg(st.winner.avatar, 96), h("h2", C(st.winner.name))] : null,
        h("p", won ? T("You won!") : T("{0} won this round.").replace("{0}", st.winner ? st.winner.name : "?")),
        h("button.btn", { onclick: back }, T("Back"))));
    }
    if (!st.card) return show(close, head, h("section.card.center", h("p", T("Play along on this device?")),
      h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join"))), players);
    if (st.status === "lobby") return show(close, head, h("section.card.center", h("h2", T("Waiting for the start …")),
      h("p.muted", T("Everybody joins on their own device.")), players), cardView(), host);
    shown = null;
    show(close, head,
      h("div.bingo-top", carousel, h("div.bingo-recent", h("span.small.muted", T("Before:")), ...st.recent.map(n => bingoBall(n)))),
      st.paused ? h("p.center.warn-text", "⏸ ", T("Paused")) : null,
      cardView(),
      h("div.row.center", h("button.btn.big.bingo-btn", { disabled: st.blocked_ms > 0, onclick: async () => {
        const r = await act("claim");
        if (r && r.bingo === false && !r.late) toast(T("Not a bingo yet – check your card!"), "bad");
      } }, st.blocked_ms > 0 ? "⏳ " + Math.ceil(st.blocked_ms / 1000) + " s" : "BINGO!")),
      players, host);
    tickCarousel();
  }
  function cardView() {
    const marks = new Set(st.marks || []);
    return h("div.bingo-card", { translate: "no" },
      ..."BINGO".split("").map((l, i) => h("div.bh", { style: { "--b": BINGO_COLORS[i] } }, l)),
      ...st.card.map((n, i) => n === 0 ? h("div.bc.free.on", "★") :
        h("button.bc" + (marks.has(i) ? ".on" : ""), { onclick: async e => {
          e.currentTarget.classList.toggle("on");
          try { const r = await api("community/bingo/mark", { method: "POST", body: { cell: i } }); st.marks = r.marks; lastSig = ""; } catch (err) { toast(err.message, "bad"); }
        } }, String(n))));
  }
  anim = setInterval(tickCarousel, 150);
  poll();
}

async function bingoCard() {
  const c = S.me && S.me.community, b = c && c.bingo;
  return h("section.card.quiz-card", h("h2", "🎱 Bingo"),
    b ? [h("p", b.status === "lobby" ? T("A game is waiting – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("bingo") }, "🙋 ", b.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("Everybody gets a card, the balls come by themselves – mark your numbers and shout «Bingo!».")),
         h("button.btn", { onclick: () => bingoStartDialog(() => go("bingo")) }, "▶ ", T("Start bingo"))]);
}
