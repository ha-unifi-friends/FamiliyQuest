// «Verbotene Wörter» – the live explaining game for the family: one explains a word without the forbidden words, the
// others guess aloud – everybody on their own device, guests via QR code (familyquest/verboten.py).
// verbotenLive(box, me, back) runs the family table, verbotenStartDialog(onStarted) sets the rules. The server keeps
// the clock and the score; the app shows the card only to who gets it from the server (the explainer and – with
// teams – the other team) and sends the number of the card with every tap.
"use strict";

const VW_ICON = "🚫";
const vwName = () => I18N.tr(T("Forbidden Words"));
const vwCoins = list => list.join(" / ") + " 🪙";
const VW_LEVELS = { easy: ["🐣", T("Easy (younger children)")], normal: ["🦊", T("Normal")], mixed: ["🎲", T("Mixed")] };
const VW_TEAMS = ["🟣", "🟠"];
const VW_POLL_MS = 700;
const vwTeam = k => VW_TEAMS[+k] + " " + I18N.tr(T("Team {0}")).replace("{0}", k === "1" ? "B" : "A");

function verbotenRulesView(rules, rewards) {
  const items = [T("One player explains a word – without saying the word itself or the 5 forbidden words on the card. The others guess aloud."),
    T("With 4 or more players two teams play: the team of the explainer guesses, the other team sees the card and watches for forbidden words («Buzz»)."),
    T("With 2 or 3 players everybody plays for themselves: the explainer taps who guessed it – both get a point."),
    I18N.tr(T("«Got it»: +1 · «Forbidden word» or «Buzz»: −1 · «Skip»: next card")) + (rules && rules.skip_penalty ? " (−1)" : ""),
    T("The time runs on the server – when it is up, the card on the table does not count and the next one explains."),
    rewards ? I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", vwCoins(rewards)) : null,
    T("Coins only at a table with at least two people of the family – not for guests.")].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

async function verbotenStartDialog(onStarted) {
  let r = {};
  try { r = await api("community/verboten/rules"); } catch {}
  const counts = r.counts || {};
  let level = VW_LEVELS[r.level] ? r.level : "mixed";
  const grid = h("div.wb-cats");
  const drawLevels = () => grid.replaceChildren(...Object.entries(VW_LEVELS).map(([k, [ic, label]]) => h("button.wb-cat" + (k === level ? ".on" : ""),
    { type: "button", "aria-pressed": String(k === level), onclick: () => { level = k; drawLevels(); } },
    h("span.wb-cat-ic", ic), h("span", label, h("small.muted.vw-n", (k === "mixed" ? (counts.easy || 0) + (counts.normal || 0) : counts[k] || "?") + " 🃏")))));
  drawLevels();
  const seg = (list, cur, label, set) => {
    const box = h("div.seg");
    const draw = () => box.replaceChildren(...list.map(n => h("button" + (n === cur ? ".on" : ""), { type: "button", onclick: () => { cur = n; set(n); draw(); } }, label(n))));
    draw();
    return box;
  };
  let time = r.time || 60, rounds = r.rounds || 2, pen = r.skip_penalty || 0;
  const teams = h("input", { type: "checkbox", checked: r.teams !== false });
  const rw = r.rewards || [0, 0, 0];
  const coins = rw.some(x => x > 0) ? h("p.small.pj-coins", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", vwCoins(rw)), h("br"),
    h("span.muted", T("Coins only at a table with at least two people of the family – not for guests."))) : null;
  const m = modal(h("div.form", h("h2", VW_ICON, " ", vwName()),
    h("p.small.muted", T("Explain the word – but do not say the forbidden words! Live on every device, 2 to 8 players.")),
    h("div.field", h("b", T("Cards")), grid),
    h("div.grid2", h("div.field", h("b", T("Time per turn")), seg(r.times || [30, 45, 60, 90, 120], time, n => n + " s", n => { time = n; })),
      h("div.field", h("b", T("Everybody explains")), seg(r.rounds_choice || [1, 2, 3, 4], rounds, n => n + "×", n => { rounds = n; }))),
    h("div.field", h("b", T("Skip costs")), seg([0, 1], pen, n => n ? "−1" : I18N.tr(T("nothing")), n => { pen = n; })),
    h("div.cards-rules", h("label.check", teams, T("Two teams with 4 or more players"))),
    coins,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      try { await api("community/verboten/start", { method: "POST", body: { level, time, rounds, teams: teams.checked, skip_penalty: pen } }); m.close(); onStarted(); }
      catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
}

function verbotenLive(box, me, back) {
  let st = null, timer = null, tick = null, alive = true, lastSig = "", cheered = false, busy = false;
  let deadlineAt = null, lastPhase = null, lastCount = null;
  const myId = String(me.id);
  box.classList.add("vw-live");
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => {
    alive = false; clearTimeout(timer); clearInterval(tick);
    box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open");
  };
  window.addEventListener("hashchange", stop, { once: true });
  const act = async (path, body) => {
    if (busy) return null;
    busy = true;
    try { const x = await api("community/verboten/" + path, { method: "POST", body }); st = x; draw(true); return x; }
    catch (e) { toast(e.message, "bad"); try { st = await api("community/verboten"); draw(true); } catch {} return null; }
    finally { busy = false; }
  };
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try { st = await api("community/verboten"); draw(); } catch {}
    timer = setTimeout(poll, VW_POLL_MS);
  }
  const player = id => (st.players || []).find(p => p.id === id) || {};
  const who = id => player(id).name || "?";
  const medal = n => ["🥇", "🥈", "🥉"][n - 1] || n + ".";
  const fill = (key, ...xs) => { let s = I18N.tr(key); xs.forEach((x, i) => { s = s.replace("{" + i + "}", x); }); return s; };
  const mark = (result, guesser) => act("mark", { n: st.n, result, guesser });

  // «Invite guests» (☰ and the button in the lobby box): the game key – null for solo tables, guests, finished games
  function invite() { return !me.guest && st.status !== "done" ? "verboten" : null; }
  function draw(force) {
    if (!alive || !box.isConnected) return;
    if (st && !Array.isArray(st.players)) st = null;

    turnCue("verboten", st && st.phase === "ready" && st.me_explainer);
    if (st && st.phase === "explain" && st.left_ms != null) deadlineAt = Date.now() + st.left_ms;
    const sig = JSON.stringify(st, (k, v) => k === "left_ms" ? undefined : v);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    clearInterval(tick);
    if (!st) return show(h("section.card.center", h("div.big-ic", VW_ICON), h("h2", T("No game right now")), noTableActions("verboten", back)));
    sounds();
    if (st.phase !== "lobby") starterBanner(st.starter, "verboten");
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    if (st.phase === "done") return show(head(), result());
    if (!st.joined && st.phase === "lobby") return show(close, head(), h("section.card.center", h("p", T("Play along on this device?")),
      h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join"))), seats(), hostBar());
    if (st.phase === "lobby") return show(close, head(), h("section.card.center", h("h2", T("Waiting for the start …")),
      h("p.muted", T("Everybody joins on their own device – at least two players.")), seats(), inviteBtn(invite()), ruleChips(),
      st.coins_on ? h("p.small", "🪙 ", fill(T("Coins for places 1 / 2 / 3: {0}"), vwCoins(st.rewards))) : null), hostBar());
    if (st.phase === "ready") return show(close, head(), scoreBar(), ready(), hostBar());
    show(close, head(), turn(), hostBar());
    tick = setInterval(clock, 200); clock();
  }

  function sounds() {
    const c = st.phase === "explain" && st.count ? st.count : null;
    if (c && lastCount && lastPhase === "explain") {
      if (c.got > lastCount.got) { try { Sound.play("right"); } catch {} }
      else if (c.taboo + c.buzz > lastCount.taboo + lastCount.buzz) { try { Sound.play("wrong"); } catch {} }
    }
    if (st.phase !== lastPhase) {
      if (st.phase === "ready" && lastPhase === "explain") { try { Sound.play("done"); } catch {} }
      lastPhase = st.phase;
    }
    lastCount = c;
  }

  function head() {
    // ☰: rules, guests, the actions of whoever leads (mix, skip, end), language
    const lead = isHost() && st.status !== "done";
    const playing = st.phase === "ready" || st.phase === "explain";
    const menu = gameMenu({ rules: () => verbotenRulesView(st.rules, st.coins_on ? st.rewards : null),
      invite: invite(),
      actions: [
        { ic: "🔀", label: T("Mix teams"), hidden: !lead || st.phase !== "lobby" || !st.teams, onclick: () => act("mix") },
        { ic: "⏭", label: T("Skip turn"), hidden: !lead || !playing,
          onclick: async () => { if ((await confirmDialog(I18N.tr(T("Skip the turn of {0}?")).replace("{0}", who(st.explainer))))) act("skip"); } },
        { ic: "⏹", label: T("End the game"), danger: true, hidden: !lead, confirm: T("End the game? The points so far count."), onclick: () => act("end") }],
      onLeave: st.status !== "done" ? () => { stop(); back(); } : null });
    return h("div.quiz-head.dm-head.vw-head", h("div.row.head-title", menu, h("h1", VW_ICON, " ", vwName())), h("div.row",
      st.phase !== "lobby" && st.phase !== "done" ? h("span.chip", { title: I18N.tr(T("Round {0} of {1}")).replace("{0}", st.round).replace("{1}", st.rounds) }, st.round + " / " + st.rounds) : null));
  }

  function ruleChips() {
    const lv = VW_LEVELS[st.rules.level] || VW_LEVELS.mixed;
    return h("div.sl-chips", h("span.chip", lv[0], " ", lv[1]), h("span.chip", "⏱ ", st.rules.time + " s"),
      h("span.chip", "🗣️ ", fill(T("Everybody explains {0}×"), st.rules.rounds)),
      h("span.chip", "⏭ ", st.rules.skip_penalty ? T("Skip: −1") : T("Skip: free")),
      st.teams ? h("span.chip", "👥 ", T("Teams")) : h("span.chip", "🙋 ", T("Everybody for themselves")));
  }

  // only the main action stays as a big button – everything else is in ☰
  function hostBar() {
    if (!(isHost() && st.status !== "done" && st.phase === "lobby")) return null;
    return h("div.row.center.host-bar",
      h("button.btn", { disabled: st.players.length < 2, onclick: async () => {
        if (busy) return;
        busy = true;
        try { const r = await beginGame("community/verboten/begin", st.players); if (r) { st = r; draw(true); } }
        catch (e) { toast(e.message, "bad"); }
        finally { busy = false; }
      } }, "▶ ", T("Start")));
  }

  function seat(p) {
    return h("div.dm-seat" + (p.id === myId ? ".dm-me" : ""), avatarSvg(p.avatar || {}, 30), C(p.name, "strong.small.dm-name"));
  }

  function seats() {
    if (!st.teams) return h("div.dm-seats", ...st.players.map(seat));
    return h("div.vw-teams", ...["0", "1"].map(k => h("div.vw-team.vw-t" + k, h("b", vwTeam(k)),
      h("div.dm-seats", ...st.players.filter(p => p.team === k).map(seat)))));
  }

  // the score: two teams side by side – alone, everybody with their points
  function scoreBar() {
    if (st.teams) return h("div.vw-score", ...["0", "1"].map(k => h("div.vw-sc.vw-t" + k + (k === st.my_team ? ".mine" : "") + (player(st.explainer).team === k ? ".on" : ""),
      h("span", vwTeam(k)), h("b", String((st.scores || {})[k] || 0)))));
    return h("div.vw-score.solo", ...st.players.map(p => h("div.vw-sc" + (p.explainer ? ".on" : "") + (p.id === myId ? ".mine" : ""),
      avatarSvg(p.avatar || {}, 20), C(p.name, "span.vw-sc-name"), h("b", String(p.total)))));
  }

  // ---------- before the turn: the explainer taps «Go!»
  function ready() {
    const p = player(st.explainer);
    const guessers = st.teams ? fill(T("{0} guesses"), vwTeam(p.team)) : T("Everybody else guesses.");
    const nextBox = st.next && !st.me_explainer && st.next === myId ? h("p.small.vw-soon", "⏭ ", T("You explain after that – get ready!")) : null;
    const main = st.me_explainer
      ? h("section.card.center.vw-ready.me", h("h2", "🗣️ ", T("Your turn to explain!")),
        h("p.muted", st.teams ? fill(T("Your team ({0}) guesses."), vwTeam(p.team)) : T("Everybody else guesses.")),
        h("p.small", T("Do not say the word, parts of it or the forbidden words. No gestures, no sounds.")),
        h("button.btn.big.vw-go", { onclick: () => act("go") }, "▶ ", T("Go!")),
        h("p.small.muted", fill(T("{0} seconds"), st.rules.time)))
      : h("section.card.center.vw-ready", avatarSvg(p.avatar || {}, 64), h("h2", fill(T("{0} explains next"), who(st.explainer))),
        h("p.muted", guessers), nextBox,
        st.teams && st.my_team && st.my_team !== p.team ? h("p.small", "👀 ", T("You will see the card – watch for forbidden words and buzz!")) : null);
    return [main, lastTurn(st.last)];
  }

  function cardLine(c) {
    const ic = { got: "✅", taboo: "🚫", buzz: "🔔", pass: "⏭" }[c.res] || "•";
    return h("li.vw-cl.vw-r-" + c.res, h("span", ic), C(c.word, "span.grow"), c.by && c.res === "got" ? h("small.muted", "→ ", C(who(c.by))) : c.by ? h("small.muted", "🔔 ", C(who(c.by))) : null,
      h("b", c.pts > 0 ? "+" + c.pts : String(c.pts)));
  }

  function lastTurn(e) {
    if (!e) return null;
    const pts = e.points > 0 ? "+" + e.points : String(e.points);
    return h("section.card.vw-last", h("div.row", h("b.grow", fill(T("{0} explained"), who(e.explainer))),
      e.side && st.teams ? h("small.vw-side", vwTeam(e.side)) : null, h("b.vw-pts", pts)),
      e.cards.length ? h("ul.vw-cards", ...e.cards.map(cardLine)) : h("p.small.muted", e.skipped ? T("Skipped") : T("No card this turn.")),
      e.open ? h("p.small.muted", "⏰ ", fill(T("Time was up at: {0}"), e.open)) : null);
  }

  // ---------- the turn
  function timeBox() {
    return h("div.vw-time", h("div.vw-bar", h("i")), h("b.vw-secs"));
  }

  function clock() {
    if (!alive || !st || st.phase !== "explain") return;
    const left = deadlineAt == null ? 0 : Math.max(0, deadlineAt - Date.now());
    const pct = Math.max(0, Math.min(100, left / (st.time_ms || 1) * 100));
    box.querySelectorAll(".vw-secs").forEach(x => { x.textContent = String(Math.ceil(left / 1000)); });
    box.querySelectorAll(".vw-bar i").forEach(x => { x.style.width = pct + "%"; });
    const t = box.querySelector(".vw-turn");
    if (t) t.classList.toggle("hurry", left < 10000);
  }

  function counts() {
    const c = st.count || {};
    return h("div.vw-count", h("span", "✅ ", String(c.got || 0)), h("span", "🚫 ", String((c.taboo || 0) + (c.buzz || 0))), h("span", "⏭ ", String(c.pass || 0)));
  }

  function theCard(big) {
    return h("div.vw-card" + (big ? ".big" : ""), h("div.vw-word", C(st.card.word)),
      h("div.vw-tabu-h", "🚫 ", T("Do not say:")),
      h("ul.vw-tabu", ...st.card.taboo.map(w => h("li", C(w)))));
  }

  function turn() {
    const p = player(st.explainer);
    if (st.me_explainer && st.card) {
      const got = () => {
        if (st.teams) return mark("got");
        const others = st.players.filter(x => x.id !== myId);
        if (others.length === 1) return mark("got", others[0].id);
        const m = modal(h("div.form.vw-pick", h("h2", "✅ ", T("Who guessed it?")),
          h("div.vw-pick-grid", ...others.map(o => h("button.btn.big", { onclick: () => { m.close(); mark("got", o.id); } }, avatarSvg(o.avatar || {}, 28), " ", C(o.name)))),
          h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel"))));
      };
      return h("div.vw-turn.explainer", h("div.vw-top", timeBox(), scoreBar()), theCard(true),
        h("div.vw-acts", h("button.btn.vw-got", { onclick: got }, "✅ ", T("Got it")),
          h("button.btn.vw-taboo", { onclick: () => mark("taboo") }, "🚫 ", T("Forbidden word")),
          h("button.btn.vw-pass", { onclick: () => mark("pass") }, "⏭ ", T("Skip"), st.rules.skip_penalty ? " (−1)" : "")),
        counts());
    }
    if (st.card) return h("div.vw-turn.watcher", h("div.vw-top", timeBox(), scoreBar()),
      h("p.small.center.vw-who", fill(T("{0} explains – watch for forbidden words!"), who(st.explainer))), theCard(false),
      st.can_buzz ? h("button.btn.vw-buzz", { onclick: () => mark("buzz") }, "🔔 ", T("Buzz! Forbidden word")) : null,
      st.turn_cards && st.turn_cards.length ? h("ul.vw-cards.small", ...st.turn_cards.slice(-3).reverse().map(cardLine)) : null);
    const mine = st.teams ? st.my_team === p.team : st.joined;
    return h("div.vw-turn.guesser", h("div.vw-top", timeBox(), scoreBar()),
      h("section.card.center.vw-guess", avatarSvg(p.avatar || {}, 72), h("h2", fill(T("{0} explains"), who(st.explainer))),
        h("div.vw-bigsecs", h("b.vw-secs")),
        h("p.vw-call", mine ? "🗣️ " + I18N.tr(T("Guess aloud!")) : I18N.tr(T("Listen …"))), counts()));
  }

  // ---------- the end
  function result() {
    clearInterval(tick);
    const mine = player(myId);
    if (mine.place === 1 && !cheered) { cheered = true; confetti(); try { Sound.play("done"); } catch {} }
    const order = (st.ranking || st.players.map(p => p.id)).map(player);
    const log = st.log || [];
    let title;
    if (!log.length) title = T("No turn was played");
    else if (st.teams) {
      const s = st.scores || {};
      title = (s["0"] || 0) === (s["1"] || 0) ? T("A draw!") : fill(T("{0} wins!"), vwTeam((s["0"] || 0) > (s["1"] || 0) ? "0" : "1"));
    } else title = C(st.players.filter(p => p.place === 1).map(p => p.name).join(" & "));
    return h("section.card.center.pj-result.vw-result",
      h("h2", "🏆 ", title),
      st.teams ? scoreBar() : null,
      h("ol.pk-rank", ...order.map(p => h("li" + (p.id === myId ? ".vw-me" : ""), h("span.pj-medal", p.place ? medal(p.place) : "–"), avatarSvg(p.avatar || {}, 30),
        h("span.grow", C(p.name, "strong"), st.teams && p.team ? h("small.muted", " " + VW_TEAMS[+p.team]) : null,
          h("small.muted", " · ✅ " + p.explained)), h("b.sl-total", String(p.total)), p.coins ? h("b.pj-plus", "+" + p.coins + " 🪙") : null))),
      log.length ? h("details.vw-log", h("summary.small", fill(T("The cards ({0})"), log.reduce((n, e) => n + e.cards.length, 0))),
        ...log.map(e => h("div.vw-log-turn", h("b.small", "🗣️ ", C(who(e.explainer)), " ", e.points > 0 ? "+" + e.points : String(e.points)),
          h("ul.vw-cards.small", ...e.cards.map(cardLine))))) : null,
      st.coins_on ? null : h("p.small.muted", T("Coins only at a table with at least two people of the family – not for guests.")),
      h("div.row.center", h("button.btn", { onclick: back }, T("Back"))));
  }
  poll();
}

async function verbotenView() {
  const box = h("div.vw-live");
  screen("games", box);
  verbotenLive(box, S.profile, () => go("games"));
}

async function verbotenFamilyCard() {
  const c = S.me && S.me.community, g = c && c.verboten;
  return h("section.card.quiz-card", h("h2", VW_ICON, " ", vwName()),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("verboten") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("Explain the word without the forbidden words – the others guess aloud. In teams or everybody for themselves.")),
         h("button.btn", { onclick: () => verbotenStartDialog(() => go("verboten")) }, "👨‍👩‍👧 ", T("Open a family table"))]);
}
