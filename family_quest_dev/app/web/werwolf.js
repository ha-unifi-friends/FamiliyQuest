// «Werwölfe» – the classic social deduction party game in one room; the app is the game master
// (familyquest/werwolf.py). werwolfLive(box, me, back) runs the family table, werwolfStartDialog(onStarted) sets the
// roles. Every phone shows only what the server tells this player: the own role (tap to reveal, hide again), the
// buttons of the active role at night, the vote by day. Who leads hears the narration (sound and – if the device can –
// a voice) and moves on when somebody is idle.
"use strict";

const WW_ICON = "🐺";
const wwName = () => I18N.tr(T("Werewolves"));
const WW_POLL_MS = 1000;
const WW_ROLES = {
  wolf: ["🐺", T("Werewolf"), T("At night you and the other werewolves choose a victim. By day you pretend to be a harmless villager.")],
  villager: ["🧑‍🌾", T("Villager"), T("No special power – listen well, talk and find the werewolves.")],
  seer: ["🔮", T("Seer"), T("Every night you may look at the role of one player. Keep it secret – or drop a hint.")],
  witch: ["🧪", T("Witch"), T("One healing potion and one poison potion for the whole game. At night you see who the werewolves chose.")],
  hunter: ["🏹", T("Hunter"), T("When you die, you take one player with you.")],
  amor: ["💘", T("Amor"), T("In the first night you choose two lovers. If one of them dies, the other dies of grief.")],
};
const WW_TALKS = [60, 120, 180, 300, 600];
const WW_FILLS = [5, 6, 7, 8, 9, 10, 11, 12];
const werwolfRoleName = k => (WW_ROLES[k] || ["", "?"])[1];
// a player's face: the avatar – or the emoji of a bot
const wwAv = (p, size) => p && p.bot
  ? h("span.bot-av", { style: { width: size + "px", height: size + "px", fontSize: (size * 0.6) + "px", background: p.color || null } }, p.emoji || "🤖")
  : avatarSvg((p && p.avatar) || {}, size);
const wwIc = k => (WW_ROLES[k] || ["❔"])[0];

function wwDeckChips(d, n) {
  if (!d) return [];
  const specials = ["seer", "witch", "hunter", "amor"].filter(k => d[k]);
  const vill = n ? Math.max(0, n - d.wolves - specials.length) : null;
  return [h("span.chip.ww-chip-wolf", "🐺 ×" + d.wolves), ...specials.map(k => h("span.chip", { title: I18N.tr(werwolfRoleName(k)) }, wwIc(k), " ", werwolfRoleName(k))),
    vill != null ? h("span.chip", "🧑‍🌾 ×" + vill) : null].filter(Boolean);
}

function werwolfRulesView(rewards) {
  const items = [T("2 to 12 people play. Fewer than 5? Bots fill the table up to 5 – they play their role by themselves."),
    T("Everybody gets a secret role on their phone. Tap the card to see it – and hide it again."),
    T("Night: everybody closes their eyes. Only the active role opens them and acts on the phone: Amor (first night), the werewolves, the seer, the witch."),
    T("The werewolves choose a victim together – they see each other's choice. When all agree, it is decided; if the leader moves on, the most votes count and a tie saves everybody."),
    T("Day: the village learns who died and sees their role. Then the village talks until the time is up."),
    T("Vote on every phone: the player with the most votes is out. A tie (or no votes): nobody is out."),
    T("The hunter takes somebody with him when he dies. Lovers die together – a werewolf and a villager in love win if they are the last two."),
    T("The village wins when all werewolves are dead. The werewolves win when there are at least as many of them as of the others."),
    T("Who is out watches quietly and sees all roles."),
    rewards ? I18N.tr(T("Coins for everybody of the family on the winning side: {0}")).replace("{0}", rewards[0] + " 🪙") : null].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

// the roles: by the number of players (recommended) or chosen by hand – start dialog and lobby
function wwRolesForm(r) {
  const s = { auto: r.auto !== false, wolves: r.wolves || 2, seer: r.seer !== false, witch: r.witch !== false, hunter: r.hunter !== false, amor: r.amor !== false, talk: r.talk || 180, fill: r.fill || 5 };
  const auto = h("input", { type: "checkbox", checked: s.auto });
  const custom = h("div.ww-custom");
  const seg = (list, cur, label, set) => {
    const box = h("div.seg");
    const draw = () => box.replaceChildren(...list.map(n => h("button" + (n === cur ? ".on" : ""), { type: "button", onclick: () => { cur = n; set(n); draw(); } }, label(n))));
    draw();
    return box;
  };
  const presets = r.presets || {};
  const table = Object.keys(presets).length ? h("div.ww-presets.small", ...Object.entries(presets).map(([n, d]) =>
    h("div", h("b", n), " ", "🐺".repeat(d.wolves), ["seer", "witch", "hunter", "amor"].filter(k => d[k]).map(wwIc).join("")))) : null;
  const drawCustom = () => {
    custom.replaceChildren(...(s.auto ? [table] : [
      h("div.field", h("b", "🐺 ", T("Werewolves")), seg([1, 2, 3], s.wolves, n => String(n), n => { s.wolves = n; })),
      h("div.ww-toggles", ...["seer", "witch", "hunter", "amor"].map(k => h("label.check", h("input", { type: "checkbox", checked: s[k], onchange: e => { s[k] = e.target.checked; } }), wwIc(k), " ", werwolfRoleName(k))))]).filter(Boolean));
  };
  auto.onchange = () => { s.auto = auto.checked; drawCustom(); };
  drawCustom();
  const form = [h("div.cards-rules", h("label.check", auto, T("Roles by the number of players (recommended)"))), custom,
    h("div.field", h("b", "☀️ ", T("Time to talk by day")), seg(r.talks || WW_TALKS, s.talk, n => n / 60 + " min", n => { s.talk = n; })),
    botsOn("werwolf") ? h("div.field", h("b", "🤖 ", T("Fill with bots up to")), seg(WW_FILLS, s.fill, n => String(n), n => { s.fill = n; }),
      h("small.muted", T("Fewer than 5? Bots fill the table.")))
      : h("p.small.muted", "🤖 ", T("Playing with bots is switched off – at least 5 people are needed."))];
  return { form, value: () => ({ ...s }) };
}

async function werwolfStartDialog(onStarted) {
  let r = {};
  try { r = await api("community/werwolf/rules"); } catch {}
  const f = wwRolesForm(r);
  const rw = r.rewards || [0, 0, 0];
  const m = modal(h("div.form", h("h2", WW_ICON, " ", wwName()),
    h("p.small.muted", T("The classic party game in one room: everybody gets a secret role on their phone, the app is the game master. 2 to 12 players, guests via QR code – bots fill the table up to 5.")),
    ...f.form,
    rw[0] > 0 ? h("p.small.pj-coins", "🪙 ", I18N.tr(T("Coins for everybody of the family on the winning side: {0}")).replace("{0}", rw[0] + " 🪙"), h("br"),
      h("span.muted", T("Coins only at a table with at least two people of the family – not for guests."))) : null,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      try { await api("community/werwolf/start", { method: "POST", body: f.value() }); m.close(); onStarted(); }
      catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
}

function werwolfLive(box, me, back) {
  let st = null, timer = null, tick = null, alive = true, lastSig = "", busy = false, cheered = false;
  let deadlineAt = null, lastKey = null, lastNight = 0, showRole = false, roleTimer = null, sel = [], heal = false, selKey = "";
  const myId = String(me.id);
  box.classList.add("ww-live");
  const isLead = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => {
    alive = false; clearTimeout(timer); clearInterval(tick); clearTimeout(roleTimer);
    box.classList.remove("quiz-full", "ww-night", "ww-day"); document.body.classList.remove("quiz-open");
  };
  window.addEventListener("hashchange", stop, { once: true });
  const act = async (path, body) => {
    if (busy) return null;
    busy = true;
    try { const x = await api("community/werwolf/" + path, { method: "POST", body }); st = x; draw(true); return x; }
    catch (e) { toast(e.message, "bad"); try { st = await api("community/werwolf"); draw(true); } catch {} return null; }
    finally { busy = false; }
  };
  const doAct = body => act("act", body);
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try { st = await api("community/werwolf"); draw(); } catch {}
    timer = setTimeout(poll, WW_POLL_MS);
  }
  const player = id => (st.players || []).find(p => p.id === id) || {};
  const who = id => player(id).name || "?";
  const fill = (key, ...xs) => { let s = I18N.tr(key); xs.forEach((x, i) => { s = s.replace("{" + i + "}", x); }); return s; };
  const openModal = view => { const m = modal(h("div", view, h("button.btn", { onclick: () => m.close() }, T("Close")))); };
  const voiceOn = () => { try { return localStorage.getItem("fq.ww.voice") !== "0"; } catch { return true; } };
  const living = () => st.players.filter(p => p.alive);

  function draw(force) {
    if (!alive || !box.isConnected) return;
    if (st && !Array.isArray(st.players)) st = null;
    if (st && st.left_ms != null) deadlineAt = Date.now() + st.left_ms;
    const sig = JSON.stringify(st, (k, v) => k === "left_ms" || k === "step_ms" ? undefined : v);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    box.classList.toggle("ww-night", !!st && (st.phase === "night" || st.phase === "roles" || (st.phase === "hunter" && st.votes == null)));
    box.classList.toggle("ww-day", !!st && ["day", "vote", "verdict"].includes(st.phase));
    clearInterval(tick);
    if (!st) return show(h("section.card.center", h("div.big-ic", WW_ICON), h("h2", T("No game right now")), noTableActions("werwolf", back)));
    const key = st.phase + ":" + (st.step || "") + ":" + st.night;
    if (key !== selKey) { selKey = key; sel = []; heal = false; }
    narrate(key);
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    if (st.phase === "done") return show(head(), result());
    if (st.phase === "lobby") return show(close, head(), lobby(), hostBar());
    let main;
    if (st.phase === "roles") main = rolesPhase();
    else if (st.phase === "night") main = night();
    else if (st.phase === "hunter") main = hunterPhase();
    else if (st.phase === "day") main = dayPhase();
    else if (st.phase === "vote") main = votePhase();
    else main = verdict();
    show(close, head(), main, hostBar());
    if (st.phase === "day") { tick = setInterval(clock, 250); clock(); }
  }

  // ---------- the narration (who leads): big text, a sound and – if wanted – a voice
  function narration() {
    const s = st.step;
    if (st.phase === "roles") return T("Everybody looks at their role secretly – and hides it again.");
    if (st.phase === "night") return { amor: T("Amor wakes up and chooses two lovers."), wolves: T("The werewolves wake up and choose their victim."),
      seer: T("The seer wakes up and looks at the role of one player."), witch: T("The witch wakes up – will she heal or poison?") }[s] || "";
    if (st.phase === "hunter") return fill(T("{0} was the hunter – and takes somebody with him!"), who(st.hunter));
    if (st.phase === "day") return (st.deaths || []).length ? T("The village wakes up – but not everybody …") : T("The village wakes up – nobody died tonight!");
    if (st.phase === "vote") return T("Time to vote: who is a werewolf?");
    if (st.phase === "verdict") return st.lynch ? fill(T("{0} is out – and was: {1}"), who(st.lynch), I18N.tr(werwolfRoleName(player(st.lynch).role))) : T("Nobody is out today.");
    return "";
  }

  function narrate(key) {
    if (key === lastKey) return;
    const first = lastKey === null;
    lastKey = key;
    if (first || !isLead() || st.phase === "lobby" || st.phase === "done") { lastNight = st.night; return; }
    let text = I18N.tr(narration());
    if (st.phase === "night" && st.night !== lastNight) text = I18N.tr(T("Night falls – everybody closes their eyes.")) + " " + text;
    lastNight = st.night;
    try { Sound.play(st.phase === "night" ? "tap" : st.phase === "day" ? "done" : "right"); } catch {}
    if (voiceOn() && text && typeof speak === "function") setTimeout(() => speak(text, document.documentElement.lang || "en"), 350);
  }

  function head() {
    const chip = st.phase === "lobby" || st.phase === "done" ? null
      : st.phase === "night" || st.phase === "roles" ? h("span.chip.ww-phase", "🌙 ", String(Math.max(1, st.night)))
      : h("span.chip.ww-phase", "☀️ ", String(st.night));
    // ☰: rules, guests (lobby), the actions of whoever leads (roles, move on when somebody is idle, voice, end), language
    const lead = isLead() && st.status !== "done";
    const skip = { night: ["⏭", T("Next")], hunter: ["⏭", T("No shot")] }[st.phase];
    const menu = gameMenu({ rules: () => werwolfRulesView(st.coins_on ? st.rewards : null),
      invite: !me.guest && st.phase === "lobby" ? "werwolf" : null,
      actions: [
        { ic: "🎭", label: T("Roles"), hidden: !lead || st.phase !== "lobby", onclick: lobbyRoles },
        { ic: skip ? skip[0] : "⏭", label: skip ? skip[1] : "", hidden: !lead || !skip, confirm: T("Move on now?"), onclick: () => act("next") },
        { ic: voiceOn() ? "🔊" : "🔇", label: T("Narrator voice on this device"), hidden: !lead || st.phase === "lobby",
          onclick: () => { try { localStorage.setItem("fq.ww.voice", voiceOn() ? "0" : "1"); } catch {} draw(true); } },
        { ic: "⏹", label: T("End the game"), danger: true, hidden: !lead, confirm: T("End the game? Nobody wins."), onclick: () => act("end") }],
      onLeave: st.status !== "done" ? () => { stop(); back(); } : null });
    return h("div.quiz-head.dm-head.ww-head", h("div.row.head-title", menu, h("h1", WW_ICON, " ", wwName())), h("div.row", chip,
      st.my_role && st.phase !== "done" ? h("button.btn.small.ghost.ww-rolebtn", { onclick: () => openModal(roleCard(true)), title: T("My role") }, "🎭") : null));
  }

  // ---------- the secret role card: tap to reveal, tap to hide (hides by itself after a while)
  function roleCard(open) {
    const card = h("button.ww-rolecard", { type: "button" });
    let shown = !!open;
    const paint = () => {
      clearTimeout(roleTimer);
      if (!shown) return card.replaceChildren(h("div.ww-back", h("span.ww-moon", "🌕"), h("b", T("Tap to see your role")), h("small", T("Nobody else may look!"))));
      const r = WW_ROLES[st.my_role] || ["❔", "?", ""];
      const extra = [];
      const wolves = st.my_role === "wolf" ? st.players.filter(p => p.role === "wolf" && p.id !== myId) : [];
      if (wolves.length) extra.push(h("p.small", "🐺 ", T("The other werewolves:"), " ", C(wolves.map(p => p.name).join(", "), "b")));
      if (st.my_lover) extra.push(h("p.small", "💘 ", fill(T("You are in love with {0}"), "«" + who(st.my_lover) + "»")));
      if (st.my_role === "amor" && st.lovers) extra.push(h("p.small", "💘 ", T("The lovers:"), " ", C(st.lovers.map(who).join(" & "), "b")));
      if (st.my_role === "seer" && st.seen && st.seen.length) extra.push(h("p.small", "🔮 ", ...st.seen.map((s, i) => h("span", i ? " · " : "", C(who(s.id), "b"), " ", wwIc(s.role)))));
      if (st.my_role === "witch" && st.potions) extra.push(h("p.small", st.potions.heal ? "💚 " : "✖️ ", T("Healing potion"), " · ", st.potions.poison ? "☠️ " : "✖️ ", T("Poison potion")));
      card.replaceChildren(h("div.ww-front.ww-r-" + st.my_role, h("span.ww-role-ic", r[0]), h("b.ww-role-name", r[1]), h("small", r[2]), ...extra,
        h("small.muted", T("Tap to hide"))));
      roleTimer = setTimeout(() => { shown = false; if (card.isConnected) paint(); }, 12000);
    };
    card.onclick = () => { shown = !shown; paint(); };
    paint();
    return card;
  }

  // ---------- the players as a grid of buttons (pick) or tiles
  function grid(list, { pick, chosen = [], badge, cls = "" } = {}) {
    return h("div.ww-grid" + cls, ...list.map(p => {
      const b = badge ? badge(p) : null;
      const attrs = pick ? { type: "button", onclick: () => pick(p) } : {};
      return h((pick ? "button" : "div") + ".ww-p" + (chosen.includes(p.id) ? ".on" : "") + (p.alive ? "" : ".dead") + (p.id === myId ? ".ww-mine" : ""), attrs,
        h("span.ww-av", wwAv(p, 30), p.alive ? null : h("i.ww-skull", "💀")), C(p.name, "span.ww-pn"), b ? h("span.ww-badge", b) : null);
    }));
  }
  const roleBadge = p => [p.role ? wwIc(p.role) : "", p.lover ? "💘" : ""].join("") || null;

  // ---------- the lobby
  function lobby() {
    const n = st.players.length, bots = st.bots || 0;
    return h("section.card.center.ww-lobby", h("h2", st.joined ? T("Waiting for the start …") : T("Play along on this device?")),
      st.joined ? null : h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join")),
      h("p.small.muted", fill(T("{0} players – {1} to {2} can play."), n, st.min_humans || 2, st.max), " ", I18N.tr(st.no_bots ? T("Playing with bots is switched off – at least 5 people are needed.") : T("Fewer than 5? Bots fill the table."))),
      grid(st.players, { cls: ".ww-seats" }),
      bots ? h("p.small.ww-bots", "🤖 ", fill(T("{0} bots join when the game starts."), bots)) : null,
      st.deck ? h("div.sl-chips.ww-deck", ...wwDeckChips(st.deck, n + bots), h("span.chip", "☀️ ", st.rules.talk / 60 + " min")) : null,
      st.deck_error ? h("p.small.ww-warn", "⚠️ ", T(st.deck_error)) : null,
      st.coins_on && st.rewards[0] > 0 ? h("p.small", "🪙 ", fill(T("Coins for everybody of the family on the winning side: {0}"), st.rewards[0] + " 🪙")) : null);
  }

  async function lobbyRoles() {
    let r = {};
    try { r = await api("community/werwolf/rules"); } catch {}
    const f = wwRolesForm({ ...r, ...st.rules });
    const m = modal(h("div.form", h("h2", "🎭 ", T("Roles")), ...f.form,
      h("div.row", h("button.btn", { onclick: async () => { if (await act("rules", f.value())) m.close(); } }, T("Save")),
        h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  }

  // only the main action of the moment stays as a big button – everything else is in ☰
  function hostBar() {
    if (!(isLead() && st.status !== "done")) return null;
    const nextLabel = { roles: ["🌙 ", T("Night falls")], day: ["🗳️ ", T("Vote now")], vote: ["✅ ", T("Close the vote")], verdict: ["🌙 ", T("Night falls")] }[st.phase];
    if (st.phase === "lobby") return h("div.row.center.host-bar.ww-bar",
      h("button.btn", { disabled: st.players.length < (st.min_humans || 2) || !!st.deck_error, onclick: () => act("begin") }, "▶ ", T("Start")));
    if (!nextLabel) return null;
    return h("div.row.center.host-bar.ww-bar",
      h("button.btn", { title: T("Moves on – e.g. when somebody is idle"),
        onclick: async () => { if (st.phase !== "vote" || (await confirmDialog(I18N.tr(T("Move on now?"))))) act("next"); } }, nextLabel[0], nextLabel[1]));
  }

  function leadLine() {
    return isLead() ? h("p.ww-narr", "📣 ", I18N.tr(narration())) : null;
  }

  function spectatorBox(extra) {
    return h("div.ww-spect", h("b", "💀 ", T("You are out – watch quietly, do not give anything away.")), extra || null);
  }

  // ---------- look at the roles
  function rolesPhase() {
    return h("div.ww-main.center", h("h2.ww-title", "🎭 ", T("Your secret role")), roleCard(false),
      h("p.small", T("Look at your role – then hide it again. When everybody is ready, night falls.")), leadLine());
  }

  // ---------- the night
  function sleepScreen(text) {
    return h("div.ww-sleep", h("div.ww-moonbig", "🌙"), h("h2", T("Eyes closed!")), h("p", text || I18N.tr(T("The village sleeps …"))),
      h("p.small.muted", fill(T("Night {0}"), st.night)));
  }

  function night() {
    if (st.spectator) {
      const step = { amor: "💘 " + I18N.tr(T("Amor")), wolves: "🐺 " + I18N.tr(T("The werewolves")), seer: "🔮 " + I18N.tr(T("Seer")), witch: "🧪 " + I18N.tr(T("Witch")) }[st.step] || "";
      const votes = st.wolf_votes ? Object.entries(st.wolf_votes).map(([w, t]) => h("div.small", C(who(w), "b"), " → ", C(who(t)))) : [];
      return h("div.ww-main", spectatorBox(h("p.small", "🌙 ", step)), ...votes,
        st.victim ? h("p.small", "🎯 ", fill(T("Victim: {0}"), who(st.victim))) : null,
        grid(st.players, { badge: roleBadge }), leadLine());
    }
    if (!st.my_turn) return h("div.ww-main", sleepScreen(), leadLine());
    if (st.step === "amor") return amorStep();
    if (st.step === "wolves") return wolvesStep();
    if (st.step === "seer") return seerStep();
    if (st.step === "witch") return witchStep();
    return sleepScreen();
  }

  function toggleSel(id, max) {
    sel = sel.includes(id) ? sel.filter(x => x !== id) : [...sel, id].slice(-max);
    draw(true);
  }

  function amorStep() {
    return h("div.ww-main.ww-act", h("h2.ww-title", "💘 ", T("Choose two lovers")),
      h("p.small", T("You may choose yourself. They will see it on their phone.")),
      grid(living(), { pick: p => toggleSel(p.id, 2), chosen: sel }),
      h("button.btn.big.ww-go", { disabled: sel.length !== 2, onclick: () => doAct({ action: "lovers", target: sel[0], target2: sel[1] }) }, "💘 ", T("Link them")));
  }

  function wolvesStep() {
    const votes = st.wolf_votes || {};
    const mine = votes[myId];
    const targets = living().filter(p => p.role !== "wolf");
    const wolves = living().filter(p => p.role === "wolf");
    const badge = p => {
      const by = Object.entries(votes).filter(([, t]) => t === p.id).map(([w]) => w);
      return by.length ? h("span.ww-bites", ...by.map(w => h("span.ww-bite", { title: who(w) }, wwAv(player(w), 16)))) : null;
    };
    const agree = wolves.length > 1 ? h("p.small", T("All werewolves must choose the same victim.")) : null;
    return h("div.ww-main.ww-act", h("h2.ww-title", "🐺 ", T("Choose your victim")), agree,
      grid(targets, { pick: p => doAct({ action: "bite", target: p.id }), chosen: mine ? [mine] : [], badge }),
      h("p.small.muted", fill(T("{0} of {1} werewolves have chosen"), Object.keys(votes).length, wolves.length)));
  }

  function seerStep() {
    const seen = (st.seen || []).filter(s => s.night === st.night).slice(-1)[0];
    if (st.looked && seen) {
      const r = WW_ROLES[seen.role] || ["❔", "?"];
      return h("div.ww-main.ww-act.center", h("h2.ww-title", "🔮 ", T("Your vision")),
        h("div.ww-vision", wwAv(player(seen.id), 56), C(who(seen.id), "b"), h("span.ww-role-ic", r[0]), h("b.ww-role-name", r[1])),
        h("button.btn.big.ww-go", { onclick: () => doAct({ action: "sleep" }) }, "😴 ", T("Close your eyes")));
    }
    return h("div.ww-main.ww-act", h("h2.ww-title", "🔮 ", T("Whose role do you want to see?")),
      grid(living().filter(p => p.id !== myId), { pick: p => toggleSel(p.id, 1), chosen: sel, badge: roleBadge }),
      h("button.btn.big.ww-go", { disabled: sel.length !== 1, onclick: () => doAct({ action: "look", target: sel[0] }) }, "👁️ ", T("See the role")));
  }

  function witchStep() {
    const pot = st.potions || {};
    const victim = st.victim;
    return h("div.ww-main.ww-act", h("h2.ww-title", "🧪 ", T("The witch")),
      h("p.ww-victim", victim ? ["🐺 ", fill(T("The werewolves chose {0}."), "«" + who(victim) + "»")] : T("The werewolves chose nobody.")),
      victim && pot.heal ? h("label.check.ww-heal", h("input", { type: "checkbox", checked: heal, onchange: e => { heal = e.target.checked; } }), "💚 ", T("Heal (use the healing potion)")) : null,
      pot.poison ? [h("p.small", "☠️ ", T("Poison somebody? (optional)")),
        grid(living().filter(p => p.id !== myId), { pick: p => toggleSel(p.id, 1), chosen: sel, cls: ".ww-small" })]
        : h("p.small.muted", "✖️ ", T("The poison potion is used up")),
      h("button.btn.big.ww-go", { onclick: async () => {
        if (sel[0] && !(await confirmDialog(fill(T("Poison {0}?"), who(sel[0]))))) return;
        doAct({ action: "potion", heal, poison: sel[0] || null });
      } }, "😴 ", T("Done – close your eyes")));
  }

  // ---------- the hunter
  function hunterPhase() {
    if (st.my_turn) return h("div.ww-main.ww-act", h("h2.ww-title", "🏹 ", T("You are dying – take somebody with you!")),
      grid(living().filter(p => p.id !== myId), { pick: p => toggleSel(p.id, 1), chosen: sel }),
      h("button.btn.big.ww-go", { disabled: sel.length !== 1, onclick: () => doAct({ action: "shoot", target: sel[0] }) }, "🏹 ", T("Shoot")));
    return h("div.ww-main.center", deathsBox(), h("div.ww-big", "🏹"), h("h2", fill(T("{0} was the hunter – and takes somebody with him!"), who(st.hunter))),
      st.spectator ? spectatorBox() : null, leadLine());
  }

  // ---------- the day
  function deathsBox() {
    const ds = st.deaths || [];
    if (!ds.length) return h("div.ww-deaths.none", "🌅 ", st.phase === "day" ? T("Nobody died tonight!") : T("Nobody is out."));
    const why = c => ({ love: "💔 " + I18N.tr(T("of grief")), shot: "🏹 " + I18N.tr(T("shot by the hunter")), vote: "🗳️ " + I18N.tr(T("voted out")) }[c] || "");
    return h("div.ww-deaths", ...ds.map(d => h("div.ww-death", wwAv(player(d.id), 34), h("span.grow", C(who(d.id), "b"), why(d.cause) ? h("small.muted", " ", why(d.cause)) : null),
      h("span.ww-dr", wwIc(d.role), " ", h("small", werwolfRoleName(d.role))))));
  }

  function clock() {
    if (!alive || !st || st.phase !== "day") return;
    const left = deadlineAt == null ? 0 : Math.max(0, deadlineAt - Date.now());
    const s = Math.ceil(left / 1000);
    box.querySelectorAll(".ww-secs").forEach(x => { x.textContent = Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); });
    box.querySelectorAll(".ww-tbar i").forEach(x => { x.style.width = Math.max(0, Math.min(100, left / (st.time_ms || 1) * 100)) + "%"; });
    const t = box.querySelector(".ww-timer");
    if (t) t.classList.toggle("hurry", left < 15000);
  }

  function dayPhase() {
    return h("div.ww-main", deathsBox(),
      h("div.ww-timer", h("span", "🗣️ ", T("Talk!")), h("b.ww-secs"), h("div.ww-tbar", h("i"))),
      st.spectator ? spectatorBox() : st.alive ? h("p.small.center", T("Who could be a werewolf? Discuss – then everybody votes.")) : null,
      grid(st.players, { badge: roleBadge, cls: ".ww-small" }), leadLine());
  }

  function votePhase() {
    const voted = st.voted || [];
    const n = living().length;
    const progress = h("p.small.center", "🗳️ ", fill(T("{0} of {1} have voted"), voted.length, n));
    if (!st.alive) {
      const votes = st.votes ? Object.entries(st.votes).map(([v, t]) => h("div.small", C(who(v), "b"), " → ", t ? C(who(t)) : I18N.tr(T("nobody")))) : [];
      return h("div.ww-main", st.spectator ? spectatorBox() : null, h("h2.ww-title", "🗳️ ", T("The village votes")), progress, ...votes,
        grid(st.players, { badge: p => voted.includes(p.id) ? "✅" : roleBadge(p), cls: ".ww-small" }), leadLine());
    }
    const mine = st.my_vote;
    return h("div.ww-main.ww-act", h("h2.ww-title", "🗳️ ", T("Who is a werewolf?")),
      grid(living().filter(p => p.id !== myId), { pick: p => doAct({ action: "vote", target: p.id }), chosen: mine ? [mine] : [],
        badge: p => [voted.includes(p.id) ? "✅" : "", roleBadge(p) || ""].join("") || null }),
      h("div.row.center", h("button.btn.ghost.small" + (mine === "" ? ".on" : ""), { onclick: () => doAct({ action: "vote", target: "" }) }, "🤷 ", T("Nobody")),
        mine != null ? h("small.muted", "✅ ", T("You voted – you may still change it.")) : null),
      progress, leadLine());
  }

  function verdict() {
    const votes = st.votes || {};
    const tally = {};
    Object.values(votes).forEach(t => { if (t) tally[t] = (tally[t] || 0) + 1; });
    const rows = Object.entries(tally).sort((a, b) => b[1] - a[1]).map(([t, k]) => h("span.chip", C(who(t)), " ", h("b", "×" + k)));
    const out = st.lynch;
    return h("div.ww-main.center", out ? h("div.ww-out", wwAv(player(out), 64), h("h2", fill(T("{0} is out of the game!"), who(out))),
      h("p.ww-reveal", wwIc(player(out).role), " ", werwolfRoleName(player(out).role)))
      : h("div.ww-out", h("div.ww-big", "🤝"), h("h2", T("Nobody is out today.")), h("p.small", T("A tie – or nobody voted."))),
      (st.deaths || []).length > 1 ? deathsBox() : null,
      rows.length ? h("div.sl-chips.ww-tally", ...rows) : null,
      st.spectator ? spectatorBox() : null, leadLine());
  }

  // ---------- the end
  function result() {
    const side = st.winner;
    const mine = player(myId);
    if (mine.won && !cheered) { cheered = true; confetti(); try { Sound.play("done"); } catch {} }
    const title = { village: ["☀️", T("The village wins!")], wolves: ["🐺", T("The werewolves win!")], lovers: ["💘", T("The lovers win!")] }[side]
      || ["🏁", T("The game was ended")];
    const order = [...st.players].sort((a, b) => (b.won - a.won) || (b.alive - a.alive));
    return h("section.card.center.pj-result.ww-result.ww-end-" + (side || "none"),
      h("h2", title[0], " ", title[1]),
      h("ul.ww-final", ...order.map(p => h("li" + (p.id === myId ? ".ww-me" : "") + (p.won ? ".won" : ""),
        h("span.ww-av", wwAv(p, 28), p.alive ? null : h("i.ww-skull", "💀")),
        h("span.grow", C(p.name, "strong"), p.lover ? " 💘" : ""), h("span.ww-dr", wwIc(p.role), " ", h("small", werwolfRoleName(p.role))),
        p.won ? h("b", "🏆") : null, p.coins ? h("b.pj-plus", "+" + p.coins + " 🪙") : null))),
      st.coins_on ? null : h("p.small.muted", T("Coins only at a table with at least two people of the family – not for guests.")),
      h("div.row.center", h("button.btn", { onclick: back }, T("Back"))));
  }
  poll();
}

async function werwolfView() {
  const box = h("div.ww-live");
  screen("games", box);
  werwolfLive(box, S.profile, () => go("games"));
}

async function werwolfFamilyCard() {
  const c = S.me && S.me.community, g = c && c.werwolf;
  return h("section.card.quiz-card", h("h2", WW_ICON, " ", wwName()),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("werwolf") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("Who is the werewolf? The party game for 2 to 12 players in one room – the app is the game master, bots fill the table.")),
         h("button.btn", { onclick: () => werwolfStartDialog(() => go("werwolf")) }, "👨‍👩‍👧 ", T("Open a family table"))]);
}
