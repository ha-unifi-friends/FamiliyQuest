// «Errate den Song»: a speaker of Home Assistant plays its own playlist (shuffled); who buzzes first answers, the
// others judge. songLive(box, me, back) runs the game full screen, songStartDialog(onStarted) chooses speaker and rules.
"use strict";

const SONG_ANSWERS = { both: T("Artist and title"), either: T("Artist or title"), artist: T("Only the artist"), title: T("Only the title") };

// the rules of the running game – for ☰ › Rules
function songRulesView(r) {
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small",
    h("li", I18N.tr(T("Who buzzes says: {0}")).replace("{0}", I18N.tr(SONG_ANSWERS[r.answer] || SONG_ANSWERS.both))),
    h("li", I18N.tr(T("The others judge by")), ": ", I18N.tr(r.vote === "unanimous" ? T("Unanimous") : T("Majority"))),
    h("li", T("Right: +1 point · wrong: −1 point")),
    h("li", I18N.tr(T("First to {0} points wins.")).replace("{0}", r.target)),
    h("li", I18N.tr(T("Songs at most")), ": ", String(r.max_songs))));
}

// «⏭ Nobody knows it» (skip the song, solution without points): for whoever leads while a song plays – the same
// condition for the button in the game screen and the entry in ☰
const songCanSkip = (st, leads) => !!(leads && st && st.status !== "done" && st.phase === "playing");

async function songStartDialog(onStarted) {
  let d = { ha: false, players: [], rules: {} };
  try { d = await api("community/song/players"); } catch {}
  if (!d.ha) return toast(T("Needs the connection to Home Assistant."), "bad");
  if (!d.players.length) return toast(T("No speaker found in Home Assistant."), "bad");
  const r = d.rules || {};
  const sel = (v, list) => h("select", ...list.map(([k, n]) => h("option", { value: k, selected: String(v) === String(k) }, I18N.tr(n))));
  const f = {
    player: sel(r.player || d.players[0].entity_id, d.players.map(p => [p.entity_id, p.name])),
    answer: sel(r.answer || "both", Object.entries(SONG_ANSWERS)),
    vote: sel(r.vote || "majority", [["majority", T("Majority")], ["unanimous", T("Unanimous")]]),
    target: sel(r.target || 10, [5, 10, 15, 20].map(n => [n, String(n)])),
    max_songs: sel(r.max_songs || 40, [20, 30, 40, 60].map(n => [n, String(n)])),
    reveal_delay: sel(r.reveal_delay ?? 5, [0, 3, 5, 10, 15].map(n => [n, n + " s"])),
    speaker_sound: h("input", { type: "checkbox", checked: r.speaker_sound !== false }),
    reveal_by: sel(r.reveal_by || "others", [["others", T("Everybody who did not buzz")], ["all", T("Who buzzed or the game leader")], ["leader", T("Only the game leader")]]),
  };
  const m = modal(h("div.form", h("h2", "🎵 ", T("Guess the song")),
    h("p.small.muted", T("Choose a speaker that has a playlist ready. The app switches shuffle on and plays, stops and skips – cover, artist and title come from the speaker.")),
    h("label.field", T("Speaker"), f.player),
    h("div.grid2", h("label.field", T("Who buzzes says"), f.answer), h("label.field", T("The others judge by"), f.vote),
      h("label.field", T("Points to win"), f.target), h("label.field", T("Songs at most"), f.max_songs),
      h("label.field", T("Countdown until the solution"), f.reveal_delay), h("label.field", T("Who shows the solution"), f.reveal_by)),
    h("label.check", f.speaker_sound, T("«Ping» for right and «brrr» for wrong also on the speaker (the playlist goes on)")),
    h("p.small.muted", T("Right: +1 point · wrong: −1 point. These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      try { await api("community/song/start", { method: "POST", body: { player: f.player.value, answer: f.answer.value, vote: f.vote.value,
        target: +f.target.value, max_songs: +f.max_songs.value, reveal_delay: +f.reveal_delay.value, reveal_by: f.reveal_by.value, speaker_sound: f.speaker_sound.checked } }); m.close(); onStarted(); }
      catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", T("Open the game")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
}

function songLive(box, me, back) {
  let st = null, timer = null, alive = true, lastSig = "", cheered = -1;
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => { alive = false; clearTimeout(timer); box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open"); };
  window.addEventListener("hashchange", stop, { once: true });
  const act = async (path, body) => {
    try { st = await api("community/song/" + path, { method: "POST", body }); draw(true); } catch (e) { toast(e.message, "bad"); }
  };
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try { st = await api("community/song"); draw(); } catch {}
    timer = setTimeout(poll, 800);
  }
  const name = id => (st.players.find(p => p.id === id) || {}).name || "?";
  // «Invite guests» (☰ and the button in the lobby box): the game key – null for solo tables, guests, finished games
  function invite() { return !me.guest && st && st.status !== "done" ? "song" : null; }
  function draw(force) {
    if (!alive || !box.isConnected) return;                            // the game was left meanwhile: a late answer
    if (st && !Array.isArray(st.players)) st = null;                 // not a game state (e.g. after «end»): no game
    const sig = JSON.stringify(st);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!st); document.body.classList.toggle("quiz-open", !!st);
    if (!st) return show(h("section.card.center", h("div.big-ic", "🎵"), h("h2", T("No game right now")), noTableActions("song", back)));
    const close = h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕");
    // ☰: rules, guests (everybody of the family), pause / «nobody knows it» / end for whoever leads, language
    const leads = isHost() && running;
    const menu = gameMenu({ rules: () => songRulesView(st.rules),
      invite: invite(),
      actions: [
        { ic: st.paused ? "▶" : "⏸", label: st.paused ? T("Go on") : T("Pause"), hidden: !leads || st.phase !== "playing", onclick: () => act("pause", { on: !st.paused }) },
        { ic: "⏭", label: T("Nobody knows it"), hidden: !songCanSkip(st, leads), onclick: () => act("next") },
        { ic: "⏹", label: T("End the game"), danger: true, hidden: !leads, confirm: T("End the game?"), onclick: () => act("end") }],
      onLeave: () => { stop(); back(); } });
    const head = h("div.quiz-head", h("div.row.head-title", menu, h("h1", "🎵 ", T("Guess the song"))),
      st.song ? h("span.chip", I18N.tr(T("Song {0} of {1}")).replace("{0}", st.song).replace("{1}", st.rules.max_songs)) : null);
    const scores = h("section.card", h("ol.scores", ...st.players.map((p, i) => h("li" + (p.id === me.id ? ".me" : ""),
      h("b", (i + 1) + "."), avatarSvg(p.avatar || {}, 28), C(p.name, "span.grow"), h("span", String(p.points))))),
      h("p.small.muted", I18N.tr(T("First to {0} points wins.")).replace("{0}", st.rules.target)));
    // the main flow stays as buttons (start, volume, «go on» while paused, «nobody knows it», close the vote, next song) – the rest is in ☰
    const lead = leads ? h("div.row.center.host-bar",
      st.phase === "lobby" ? h("button.btn", { onclick: () => act("begin") }, "▶ ", T("Start")) : null,
      st.phase !== "lobby" ? h("span.row.song-vol", h("button.btn.ghost.small", { title: T("Quieter"), onclick: () => act("volume", { step: -1 }) }, "🔉 −"),
        h("b.small", "🔊 ", st.volume != null ? st.volume + " %" : "–"),
        h("button.btn.ghost.small", { title: T("Louder"), onclick: () => act("volume", { step: 1 }) }, "🔊 +")) : null,
      st.phase === "playing" && st.paused ? h("button.btn.small", { onclick: () => act("pause", { on: false }) }, "▶ ", T("Go on")) : null,
      songCanSkip(st, leads) ? h("button.btn.small.ghost.song-skip", { onclick: () => act("next") }, "⏭ ", T("Nobody knows it")) : null,
      st.phase === "reveal" ? h("button.btn.small", { onclick: () => act("decide") }, "⚖️ ", T("Close the vote")) : null,
      st.phase === "result" ? h("button.btn", { onclick: () => act("next") }, "⏭ ", T("Next song")) : null) : null;
    if (st.phase === "done") {
      const top = st.players[0];
      if (top && top.id === me.id && cheered !== st.game) { cheered = st.game; confetti(); try { Sound.play("done"); } catch {} }
      return show(close, head, h("section.card.center", h("h2", "🏆 ", C(top ? top.name : "")), top ? avatarSvg(top.avatar || {}, 96) : null), scores,
        h("div.row.center.host-bar", h("button.btn", { onclick: () => { stop(); back(); } }, T("Back"))));
    }
    if (!st.joined) return show(close, head, h("section.card.center", h("p", T("Play along on this device?")),
      h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join"))), scores, lead);
    if (st.phase === "lobby") return show(close, head, h("section.card.center", h("h2", T("Waiting for the start …")),
      h("p.muted", I18N.tr(T("Who buzzes says: {0}")).replace("{0}", I18N.tr(SONG_ANSWERS[st.rules.answer]))), inviteBtn(invite())), scores, lead);
    if (st.phase === "playing") return show(close, head,
      h("div.song-buzz-wrap", h("button.song-buzzer", { disabled: st.paused, onclick: () => { try { navigator.vibrate && navigator.vibrate(60); } catch {} act("buzz"); } },
        h("span", "🔔"), h("b", T("Buzz!")))),
      h("p.center.muted", st.paused ? "⏸ " + I18N.tr(T("Paused")) : I18N.tr(T("Listen … and buzz when you know it: {0}")).replace("{0}", I18N.tr(SONG_ANSWERS[st.rules.answer]))),
      scores, lead);
    if (st.phase === "buzzed") {
      const mine = st.buzzer === me.id;
      if (mine) { try { Sound.play("tap"); } catch {} }
      return show(close, head, h("section.card.center.song-turn",
        h("div.big-ic", "🔔"), h("h2", mine ? T("You buzzed first!") : I18N.tr(T("{0} buzzed first")).replace("{0}", name(st.buzzer))),
        h("p", mine ? I18N.tr(T("Say it out loud: {0}")).replace("{0}", I18N.tr(SONG_ANSWERS[st.rules.answer])) : T("Listen to the answer …")),
        countdownBtn(isHost() || (st.rules.reveal_by === "others" ? !mine : st.rules.reveal_by !== "leader" && mine))), scores, lead);
    }
    const sol = st.solution || {};
    const cover = sol.cover ? h("img.song-cover", { alt: "", onerror: e => e.target.replaceWith(h("div.song-cover.empty", "🎵")) }) : h("div.song-cover.empty", "🎵");
    if (sol.cover) fetchCover(cover);
    const solCard = h("section.card.center.song-sol", cover, h("h2", C(sol.title || "?")), h("p.song-artist", C(sol.artist || "")));
    if (st.phase === "reveal") {
      const judge = st.buzzer !== me.id;
      return show(close, head, solCard,
        h("section.card.center", h("p", I18N.tr(T("Was the answer of {0} right?")).replace("{0}", name(st.buzzer))),
          judge ? h("div.row.center", h("button.btn.good.big" + (st.my_vote === true ? ".on" : ""), { onclick: () => act("vote", { right: true }) }, "👍 ", T("Right")),
            h("button.btn.bad.big" + (st.my_vote === false ? ".on" : ""), { onclick: () => act("vote", { right: false }) }, "👎 ", T("Wrong")))
            : h("p.muted", T("The others judge your answer …")),
          h("p.small.muted", I18N.tr(T("{0} of {1} have judged")).replace("{0}", st.players.filter(p => p.voted).length).replace("{1}", st.players.length - 1))),
        scores, lead);
    }
    // result
    const v = st.verdict;
    // everybody hears the verdict once per song: «ping» for right, «brrr» for wrong
    if (v && v.right != null && cheered !== st.song) { cheered = st.song; try { if (Sound.on) new Audio("sounds/" + (v.right ? "right" : "wrong") + ".mp3").play().catch(() => Sound.play(v.right ? "right" : "wrong")); } catch {} }
    return show(close, head, solCard,
      h("section.card.center", st.skipped ? h("p.muted", T("Nobody knew it – no points.")) : v && v.right == null ? h("p.muted", T("Nobody has judged – no points.")) : v ? h("p.quiz-msg" + (v.right ? ".good" : ""),
        v.right ? I18N.tr(T("Right! +1 for {0}")).replace("{0}", name(st.buzzer)) : I18N.tr(T("Not quite – −1 for {0}")).replace("{0}", name(st.buzzer))) : null,
        !isHost() ? h("p.small.muted", T("The game leader starts the next song.")) : null),
      scores, lead);
  }
  // «show the solution» only after the countdown (game rule, default 5 s): first say the answer, then look
  function countdownBtn(may) {
    const end = Date.now() + (st.reveal_in_ms || 0);
    const btn = h("button.btn.big", { onclick: () => act("reveal") });
    const wait = h("p.song-count");
    const tickFn = () => {
      const left = Math.ceil((end - Date.now()) / 1000);
      if (left > 0) { btn.disabled = true; btn.textContent = "⏳ " + left; wait.textContent = "⏳ " + left; return; }
      clearInterval(cd); btn.disabled = false; btn.replaceChildren("👀 ", I18N.tr(T("Show the solution"))); wait.textContent = "";
    };
    const cd = setInterval(() => { if (!btn.isConnected && !wait.isConnected) return clearInterval(cd); tickFn(); }, 250);
    tickFn();
    return may ? btn : wait;
  }
  // the cover comes through the app (it needs the login header)
  async function fetchCover(img) {
    try {
      const r = await fetch("api/community/song/cover", { headers: Auth.kid ? { "X-FQ-Token": Auth.kid } : Auth.parent ? { "X-FQ-Parent": Auth.parent } : {} });
      if (!r.ok) throw 0;
      img.src = URL.createObjectURL(await r.blob());
    } catch { img.replaceWith(h("div.song-cover.empty", "🎵")); }
  }
  poll();
}

async function songView() {
  const box = h("div.song-live");
  screen("games", box);
  songLive(box, S.profile, () => go("games"));
}

async function songFamilyCard() {
  const c = S.me && S.me.community, g = c && c.song;
  return h("section.card.quiz-card", h("h2", "🎵 ", T("Guess the song")),
    g ? [h("p", g.status === "lobby" ? T("A game is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("song") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("A speaker plays songs – who buzzes first and knows artist and title gets a point.")),
         h("button.btn", { onclick: () => songStartDialog(() => go("song")) }, "▶ ", T("Open the game"))]);
}
