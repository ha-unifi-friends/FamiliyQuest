// «Beat the Bureaucracy» (familyquest/stempeljagd.py, internal key "stempeljagd") – a light-hearted family party game
// in the town hall of an invented town: get all stamps for your building project. The server decides everything;
// this file draws the town hall (CSS), the scenes at the counters, the mini-games and the permit certificate.
const SJ_ICON = "🏛️";
const sjName = () => I18N.tr(T("Beat the Bureaucracy"));
const sjTown = () => I18N.tr(T("Little Red-Tapington"));
const sjCoins = list => list.join(" / ") + " 🪙";
const SJ_COLORS = ["#e8590c", "#1971c2", "#2f9e44", "#9c36b5", "#495057"];
const SJ_DESK = {
  info: ["ℹ️", "1", T("General information"), "🧑‍💼"], building: ["🏗️", "2", T("Office for Building Matters"), "👷"],
  green: ["🌳", "3", T("Office for Green Spaces"), "🧑‍🌾"], slow: ["🐌", "4", T("Commission for Slowness"), "🧓"],
  archive: ["🗄️", "−1", T("Archive in the basement"), "🦉"], coffee: ["☕", "", T("Coffee kitchen"), "🫖"] };
const SJ_PROJECTS = {
  treehouse: ["🌳", T("Tree house with a rope ladder"), T("The tree house is far too cheerful."), T("We paint it a more serious grey.")],
  slide: ["🛝", T("Garage with a water slide"), T("The slide does not fit the townscape."), T("We paint the slide beige.")],
  pizza: ["🍕", T("Pizza oven in the garden"), T("The pizza oven casts a shadow on our garden gnome."), T("The gnome gets a free pizza every Friday.")],
  hamster: ["🐹", T("Hamster palace with three floors"), T("The hamster palace is taller than our letterbox."), T("The hamster promises to wave politely.")],
  duck: ["🦆", T("Pond for exactly one duck"), T("The duck quacks in the wrong key."), T("The duck takes singing lessons.")],
  lemonade: ["🍋", T("Lemonade stand with a drive-through"), T("The lemonade is too sour for the neighbourhood."), T("We add one extra spoon of sugar.")],
  igloo: ["🧊", T("Igloo with a doorbell"), T("The igloo doorbell plays an unapproved tune."), T("The doorbell only hums, very quietly.")],
  rocket: ["🚀", T("Garden shed shaped like a rocket"), T("The shed could take off at any moment."), T("We tie it down with a very long rope.")] };
const SJ_CARDS = {
  i_refer4: T("Not responsible – please go to counter 4."), i_refer3: T("That is Green Spaces. Counter 3: down the hall, left, left again."),
  i_refer2: T("Building matters? Counter 2. Unless it is Wednesday."), i_know: T("I don't know – but I know someone who doesn't know either. Counter 3."),
  i_self: T("The clerk smiles kindly and refers you on – to counter 1."), i_map: T("Here is a map of the town hall. Outdated, but nicely laminated."),
  i_yes: T("Oh! I am responsible after all. Stamp!"), i_brochure: T("Take this brochure: «How to read brochures»."),
  i_expired: T("Your waiting number has expired. It was valid for 3 seconds."), i_speak: T("Please listen carefully to the regulation."),
  b_received: T("Your application has been received."), b_double: T("Approved! Even the stamp is surprised."),
  b_b12: T("Form B-12 in triplicate, blue only."), b_copy: T("We need a certified copy of the original."),
  b_original: T("We need the original of the certified copy."), b_holiday: T("The person in charge is on holiday. So is the substitute."),
  b_lunch: T("Lunch break! The shutter comes down."), b_selfstamp: T("The stamp is right there – stamp it yourself, but neatly!"),
  b_article: T("According to the regulations …"), b_refer1: T("Please start with general information. Counter 1."),
  b_ink: T("The stamp pad is dry. Please come back after it has rained."),
  g_tree: T("Does the tree agree?"), g_birds: T("The birds were asked too. They said yes!"), g_leaves: T("Please count all the leaves of the tree and fill in the form."),
  g_refer2: T("Building? That is counter 2. Trees don't build."), g_refer4: T("This has to go to the Commission for Slowness first. Counter 4."),
  g_shadow: T("Your shadow is 3 cm too long. Please come back at noon."), g_map: T("We need a map of the garden, drawn with a ruler."),
  g_worm: T("An earthworm filed an objection – and withdrew it. Stamp!"), g_grumpy: T("The clerk is grumpy today: «Too green!»"),
  g_lunch: T("Watering break! The shutter comes down."), g_goldfish: T("We need proof that your goldfish lives with you."),
  s_approved: T("After four hours of deliberation: approved!"), s_postponed: T("Postponed to the next meeting."),
  s_vote: T("Vote: 3 for, 0 against, 12 asleep. Approved!"), s_refer1: T("Please first ask counter 1 whether you may ask us."),
  s_confirm: T("Please confirm that you confirmed this confirmation."), s_break: T("The commission takes a coffee break. A long one."),
  s_slowstamp: T("Stamp … ing … in … pro … gress … done!"), s_sleep: T("We need a certificate of good sleep.") };
const SJ_DOCS = { b12: T("Form B-12 (blue)"), copy: T("Certified copy"), original: T("The original"), goldfish: T("Goldfish certificate"),
  map: T("Garden map (with a ruler)"), sleep: T("Certificate of good sleep"), confirm: T("Confirmation of the confirmation"), greeting: T("Friendly greeting card") };
const SJ_TRICKS = {
  appointment: ["📅", T("Appointment"), T("Answer «Yes» to «Do you have an appointment?»")],
  croissant: ["🥐", T("Croissants"), T("Opens almost every door – and the clerk's good mood draws two cards: the better one counts.")],
  connections: ["🤝", T("Connections"), T("A sure way in – or cancel a referral.")],
  gift: ["💌", T("Small gift"), T("+2 stamps – but the order inspector catches it with 35 %: a fine and back to counter 1. (Only in this game! In real life friendliness and patience work better.)")],
  folder: ["📎", T("Complete folder"), T("Protects once against «something is missing».")],
  friendly: ["🗣️", T("Stay friendly"), T("The next grumpy clerk melts: a stamp instead.")],
  objection: ["⚖️", T("Objection"), T("Object to another team's project: if their defence fails, it costs them a stamp.")],
  mayor: ["📣", T("Talk to the mayor"), T("+1 stamp and all referrals are forgotten – once per game.")] };
const SJ_ARGS = { polite: ["🙏", T("Insist politely"), T("«Politely noted. And politely refused.»")],
  urgent: ["⏰", T("It's urgent!"), T("«Everything is urgent here. That is why it takes so long.»")],
  tiny: ["🤏", T("Only a tiny question"), T("«Tiny questions have the biggest answers. Come back in spring.»")],
  croissant: ["🥐", T("Offer croissants"), T("«Croissants? I'm on a diet. Since this morning.»")],
  connections: ["🤝", T("My cousin works here"), T("«Your cousin? He is on holiday. Like everybody.»")] };
const SJ_CHEATS = { toilet: ["🚽", T("«I was here before, I just went to the toilet!»"), T("Sent to the end of the queue!")],
  signature: ["✍️", T("«I only need a signature!»"), T("The queue complains loudly – your relations suffer.")],
  delivery: ["📦", T("Pretend to be a delivery person"), T("The clerk closes the counter: «Lunch break!»")],
  folder: ["🗂️", T("Carry a big folder and look official"), T("Sent to the end of the queue!")],
  stroller: ["👶", T("Push a stroller (with a doll)"), T("The queue complains loudly – your relations suffer.")],
  croissant: ["🥐", T("Share croissants with the queue"), T("Sent to the end of the queue!")] };
const SJ_MOODS = { grumpy: ["😠", T("grumpy")], sleepy: ["😴", T("sleepy")], chatty: ["💬", T("chatty")], cheerful: ["😊", T("cheerful")] };
const SJ_EVENTS = { regulation: ["📜", T("New regulation: all forms in the folders are invalid!")],
  migration: ["💻", T("System migration: this round the computer says no to every stamp.")],
  openday: ["🎉", T("Open day: all counters are open – no queues, no appointments!")] };
const SJ_RUMOURS = { r_building: T("Rumour: the building office opens again in {0} rounds."), r_commission: T("Rumour: the commission meets in {0} rounds."),
  r_cat: T("Rumour: a cat lives in the archive and files everything under «C»."), r_croissant: T("Rumour: the mayor loves croissants."),
  r_tree: T("Rumour: the tree says yes more often on Fridays."), r_stamp: T("Rumour: the new stamp at counter 2 is very loud."),
  r_plant: T("Rumour: the office plant has been on the waiting list since 1987."), r_counter4: T("Rumour: counter 4 has never been seen open. But it exists.") };
const SJ_ADMIN = { a_refer: ["↪️", T("Referral"), T("The team must go to another counter next.")], a_lunch: ["🍽️", T("Lunch break"), T("The team misses its next turn.")],
  a_regulation: ["📜", T("New regulation"), T("The team's documents are invalid.")], a_form: ["📝", T("Absurd form"), T("The team must fill in a form first.")],
  a_revoke: ["❌", T("Signature missing"), T("One stamp is revoked.")] };
const SJ_CHATTER = [T("What are you doing at the weekend?"), T("Nothing. And you?"), T("The coffee machine is making that noise again."),
  T("Have you watered the plant?"), T("It's plastic. I water it anyway."), T("Look, my holiday photos!"), T("That's a stamp. On holiday?"),
  T("Is it lunch yet?"), T("In 4 hours and 12 minutes."), T("Did you see the new stapler?"), T("My cat has a new hobby: sleeping."),
  T("Who took my yellow pen?"), T("Shall we tidy the forms?"), T("Tomorrow. Or the day after."), T("Is someone waiting?"), T("No idea, I'm not looking.")];
const SJ_DAYS = [T("Monday"), T("Tuesday"), T("Wednesday"), T("Thursday"), T("Friday")];
const SJ_MOON = ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"];
const SJ_BOXES = { confirmed: T("I confirm that I confirmed this confirmation."), read: T("I have read what I did not read."),
  robot: T("I am not a robot, just very tidy."), agree: T("I agree to agree."), hamster: T("My hamster agrees too."),
  pen: T("I filled this in with a pen that writes."), today: T("Today is today."), copies: T("I want this form in triplicate.") };
const SJ_ITEMS = { pancake: T("pancake"), waffle: T("waffle"), pretzel: T("pretzel"), muffin: T("muffin"), noodle: T("noodle"),
  jellyfish: T("jellyfish"), bagel: T("bagel"), dumpling: T("dumpling") };
const sjTr = s => I18N.tr(s);
const sjFill = (s, ...a) => a.reduce((x, v, i) => x.split("{" + i + "}").join(v), sjTr(s));
const sjDeskName = c => sjTr((SJ_DESK[c] || ["", "", "?"])[2]);
const sjDeskShort = c => SJ_DESK[c] && SJ_DESK[c][1] ? sjFill(T("Counter {0}"), SJ_DESK[c][1]) : sjDeskName(c);

// «ding-dong» – two tones on the speakers (the sound switch of the app), a buzz on phones
function sjDing() {
  if (!Sound.on) return;
  try {
    Sound.ctx = Sound.ctx || new (window.AudioContext || window.webkitAudioContext)();
    [[659, 0], [523, 0.32]].forEach(([f, d]) => {
      const o = Sound.ctx.createOscillator(), g = Sound.ctx.createGain(), t = Sound.ctx.currentTime + d;
      o.type = "sine"; o.frequency.value = f;
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.22, t + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.6);
      o.connect(g).connect(Sound.ctx.destination); o.start(t); o.stop(t + 0.65);
    });
    if (navigator.vibrate) navigator.vibrate([40, 80, 40]);
  } catch {}
}

function stempeljagdRulesView(r, rewards) {
  r = r || {};
  const n = { short: 5, normal: 7, long: 9 }[r.length] || 7;
  const items = [
    sjFill(T("Every team wants its building project approved: the permit needs {0} stamps. The first team with all stamps wins."), n),
    T("Your turn: play a trick card if you like, then tap a counter in the town hall. Counter 2 is open only on Tuesdays and at new moon; the Commission for Slowness meets every 3 rounds (in between your application goes on the pile)."),
    T("At a counter first comes the scene: «Do you have an appointment?» – without one it is fully booked, so argue (the clerk's mood matters). Or there is a huge queue: wait patiently or try a trick – getting caught has funny consequences."),
    T("Then the authority card: a stamp, a referral to another counter, a missing document (fetch it in the archive, hand it in at any counter), a lunch break, a mini-game …"),
    T("The coffee kitchen gives a trick card, a rumour and better relations. Trick cards: 📅 appointment, 🥐 croissants, 🤝 connections, 💌 small gift, 📎 complete folder, 🗣️ stay friendly, ⚖️ objection – and 📣 the mayor once per game."),
    T("💌 A small gift is only a joke in this game – the order inspector often catches it. In real life friendliness and patience work much better!"),
    T("⚖️ Objection: the other team defends with an expert report (a document), neighbours' signatures or a compromise. A successful objection costs a stamp."),
    r.mode === "admin" ? T("Administration mode: one team plays the administration – it plays authority cards on the builders and opens or closes counters. It wins if nobody has the permit when the time is up.") : null,
    rewards ? sjFill(T("Coins for places 1 / 2 / 3: {0}"), sjCoins(rewards)) : null,
    T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."),
  ].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", sjTr(x)))));
}

async function stempeljagdStartDialog(solo, onStarted) {
  let r = {};
  try { r = await api("community/stempeljagd/rules"); } catch {}
  const sel = (v, list) => h("select", ...list.map(([k, n]) => h("option", { value: k, selected: String(v) === String(k) }, n)));
  const bots = sel(solo ? Math.max(1, r.bots ?? 2) : (r.bots ?? 0), (solo ? [1, 2, 3] : [0, 1, 2, 3]).map(n => [n, String(n)]));
  const level = sel(r.level || "normal", [["easy", T("easy")], ["normal", T("normal")], ["hard", T("hard")]]);
  const length = sel(r.length || "normal", [["short", sjFill(T("Short: {0} stamps"), 5)], ["normal", sjFill(T("Normal: {0} stamps"), 7)], ["long", sjFill(T("Long: {0} stamps"), 9)]]);
  const mode = sel(r.mode === "admin" ? (r.admin === "host" ? "admin_me" : "admin_bot") : "teams",
    [["teams", T("Teams against teams")], ["admin_bot", T("Family against the administration (bot)")], ["admin_me", T("I play the administration")]]);
  const projects = sel(r.projects || "pick", [["pick", T("Every team picks its project")], ["random", T("Projects at random")]]);
  const minis = h("input", { type: "checkbox", checked: r.minigames !== false });
  const picker = botPicker(r.bot_ms);
  const rw = r.rewards || [0, 0, 0];
  const coins = solo ? h("p.small.muted", "🪙 ", T("Alone against bots there are no coins."))
    : rw.some(x => x > 0) ? h("p.small.pj-coins", "🪙 ", sjFill(T("Coins for places 1 / 2 / 3: {0}"), sjCoins(rw))) : null;
  const m = modal(h("div.form", h("h2", SJ_ICON, " ", sjName(), solo ? " – " + sjTr(T("alone against bots")) : ""),
    h("p.small.muted", sjFill(T("Get every stamp for your building project in the town hall of {0} – despite counters, queues and referrals."), sjTown())),
    h("div.grid2", h("label.field", T("Bot teams"), bots), h("label.field", T("Bots play"), level),
      h("label.field", T("Game length"), length), h("label.field", T("Projects"), projects)),
    h("label.field", T("Mode"), mode),
    solo ? null : h("p.small.muted", T("2 to 4 teams – one device per team: the family joins on their own devices, guests via QR code.")),
    h("div.cards-rules", h("label.check", minis, T("Mini-games (absurd forms, stamping, bureaucratic speak)"))),
    picker.el, coins,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      const body = { solo, bots: Math.max(+bots.value, picker.ids().length), level: level.value, length: length.value, projects: projects.value,
        minigames: minis.checked, mode: mode.value === "teams" ? "teams" : "admin", admin: mode.value === "admin_me" ? "host" : "bot",
        bot_ids: picker.ids(), bot_ms: picker.ms() };
      try { await api("community/stempeljagd/start", { method: "POST", body }); m.close(); onStarted(); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", solo ? T("Play") : T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  withoutBots("stempeljagd", bots, level, picker.el);
}

function stempeljagdLive(box, me, back) {
  let st = null, timer = null, alive = true, lastSig = "", busy = false, cheered = false, seenSeq = null, seenTicket = null;
  let chatTimer = null, overlay = null, miniKey = "", skew = 0;
  const myId = String(me.id);
  box.classList.add("sj-live");
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => { alive = false; clearTimeout(timer); clearInterval(chatTimer); closeOverlay(); box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open"); };
  window.addEventListener("hashchange", stop, { once: true });
  const player = id => (st && st.players || []).find(p => p.id === id) || {};
  const who = id => player(id).name || "?";
  const color = id => SJ_COLORS[player(id).admin ? 4 : (player(id).seat ?? 0) % 4];
  const act = async (action, body = {}) => {
    if (busy) return null;
    busy = true;
    try { st = await api("community/stempeljagd/act", { method: "POST", body: { action, ...body } }); return st; }
    catch (e) { toast(e.message, "bad"); return null; }
    finally { busy = false; draw(true); }
  };
  const post = async path => { try { st = await api("community/stempeljagd/" + path, { method: "POST", body: {} }); } catch (e) { toast(e.message, "bad"); } draw(true); };
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try { const s = await api("community/stempeljagd"); if (!busy) { st = s; draw(); } } catch {}
    timer = setTimeout(poll, 900);
  }
  function closeOverlay() { if (overlay) { overlay.remove(); overlay = null; } miniKey = ""; }

  // ---------- news since the last look: ding-dong, the reluctant phone call, events, toasts for me
  function news() {
    if (st.now) skew = st.now - Date.now() / 1000;
    const d = st.display;
    if (d && seenTicket !== null && d.n !== seenTicket) { sjDing(); const b = box.querySelector(".sj-board"); if (b) { b.classList.remove("flash"); void b.offsetWidth; b.classList.add("flash"); } }
    if (d) seenTicket = d.n; else if (seenTicket === null) seenTicket = 0;
    const log = st.log || [];
    const last = log.length ? log[log.length - 1].seq : 0;
    if (seenSeq === null) { seenSeq = last; return; }
    for (const ev of log.filter(e => e.seq > seenSeq)) {
      if (ev.kind === "call") phoneCall(ev);
      else if (ev.kind === "event") toast(SJ_EVENTS[ev.event][0] + " " + sjTr(SJ_EVENTS[ev.event][1]));
      else if (ev.kind === "meeting" && Object.keys(ev.res || {}).length) toast("🐌 " + sjTr(T("The Commission for Slowness has met.")));
      else if (ev.kind === "objection" && ev.to === myId) { toast("⚖️ " + sjFill(T("{0} files an objection against your project!"), who(ev.player)), "bad"); try { Sound.play("wrong"); } catch {} }
      else if (ev.kind === "inspector") { toast("🕵️ " + sjFill(T("The order inspector caught {0}!"), who(ev.player)), ev.player === myId ? "bad" : ""); try { Sound.play("wrong"); } catch {} }
      else if (ev.kind === "admin" && ev.to === myId) toast(SJ_ADMIN[ev.card][0] + " " + sjFill(T("The administration plays «{0}» on you."), sjTr(SJ_ADMIN[ev.card][1])), "bad");
    }
    seenSeq = last;
  }
  function phoneCall(ev) {
    if (overlay) return;
    const o = h("div.sj-overlay.sj-call", h("div.sj-callbox",
      h("div.sj-phone", "☎️"), h("p.sj-callwho", SJ_DESK[ev.counter] ? SJ_DESK[ev.counter][3] : "🧑‍💼", " ", sjDeskShort(ev.counter)),
      h("p.sj-bubble", sjTr(T("«Hello? Yes … I have a citizen here who seems to be very important and wants a ticket without an appointment …»"))),
      h("p.sj-sigh", "😮‍💨 ", T("*sigh*"))));
    document.body.append(o); overlay = o;
    try { Sound.play("ding"); } catch {}
    setTimeout(() => { if (overlay === o) closeOverlay(); else o.remove(); }, 2600);
  }

  // ---------- the clerks chat (only a picture: speech bubbles over the counters)
  function chatter() {
    clearInterval(chatTimer);
    chatTimer = setInterval(() => {
      if (!alive || document.hidden) return;
      const rooms = [...box.querySelectorAll(".sj-room.desk")];
      if (!rooms.length) return;
      const busyRooms = rooms.filter(r => r.classList.contains("queue"));
      const room = (busyRooms.length && Math.random() < 0.7 ? busyRooms : rooms)[Math.floor(Math.random() * (busyRooms.length && Math.random() < 0.7 ? busyRooms.length : rooms.length))] || rooms[0];
      const b = h("span.sj-chat", sjTr(SJ_CHATTER[Math.floor(Math.random() * SJ_CHATTER.length)]));
      room.append(b);
      setTimeout(() => b.remove(), 3200);
    }, 2600);
  }

  // ---------- the screen
  function draw(force) {
    if (!alive || !box.isConnected) return;
    if (st && !Array.isArray(st.players)) st = null;
    turnCue("stempeljagd", st && st.my_turn);
    const sig = JSON.stringify(st && [st.phase, st.status, st.stage, st.turn, st.actor, st.round, st.last && st.last.seq, st.joined, st.rules,
      st.players.map(p => [p.id, (p.stamps || []).length, p.tricks, p.place]), st.mine, st.projects_taken, st.closed, st.cur && st.cur.mini && st.cur.mini.start, st.scenes]);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    if (!st) return show(h("section.card.center", h("div.big-ic", SJ_ICON), h("h2", T("No game right now")), noTableActions("stempeljagd", back)));
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    const menu = gameMenu({ rules: () => stempeljagdRulesView(st.rules, st.coins_on ? st.rewards : null),
      invite: !st.solo && !me.guest && st.status !== "done" ? "stempeljagd" : null,
      actions: [{ ic: "⏭", label: T("Help the team on turn"), hidden: !isHost() || !(st.phase === "play" || st.phase === "projects") || st.my_turn, onclick: () => post("nudge") },
        { ic: "⏹", label: T("End the game"), danger: true, hidden: !isHost() || st.status === "done", confirm: T("End the game?"), onclick: () => post("end").then(() => { stop(); back(); }) }],
      onLeave: running ? () => { stop(); back(); } : null });
    const head = h("div.quiz-head.dm-head.sj-head", h("div.row.head-title", menu, h("h1", SJ_ICON, " ", sjName())),
      st.phase === "play" ? h("span.sj-cal", { title: sjTr(T("Round")) + " " + st.round }, sjTr(SJ_DAYS[st.weekday] || ""), " ", SJ_MOON[st.moon] || "") : null);
    if (st.phase !== "lobby") starterBanner(st.starter, "stempeljagd");
    if (st.phase === "lobby") { closeOverlay(); return show(close, head, lobby()); }
    if (st.phase === "done") { closeOverlay(); clearInterval(chatTimer); return show(head, certificate()); }
    if (!st.joined) return show(close, head, seats(), hall(), h("p.muted.center", T("The game has already started")));
    news();
    if (st.phase === "projects") return show(close, head, seats(), projectPick());
    show(close, head, seats(), hall(), panel());
    miniGame();
    if (!chatTimer) chatter();
  }

  function seatIcon(p, size) {
    return p.bot ? h("span.bot-av", { style: { width: size + "px", height: size + "px", fontSize: (size * 0.6) + "px", background: p.color || null } }, p.emoji || "🤖") : avatarSvg(p.avatar || {}, size);
  }
  function lobby() {
    const r = st.rules, host = isHost() && st.status !== "done";
    const free = Array.from({ length: st.bots || 0 }, () => h("div.dm-seat.hw-botseat", h("span.bot-av", { style: { width: "30px", height: "30px", fontSize: "18px" } }, "🤖"), h("span.small.muted", T("Bot"))));
    const adm = r.mode === "admin" ? (r.admin === "bot" ? sjTr(T("a bot")) : who(r.admin)) : null;
    const chooser = host ? h("div.sj-adminpick", h("span.small.muted", "🏛️ ", T("The administration:")),
      h("div.row.wrap", h("button.btn.small" + (r.mode !== "admin" ? "" : ".ghost"), { onclick: () => setAdmin("teams") }, T("nobody (teams against teams)")),
        h("button.btn.small" + (r.mode === "admin" && r.admin === "bot" ? "" : ".ghost"), { onclick: () => setAdmin("bot") }, "🤖 ", T("a bot")),
        ...st.players.filter(p => !p.bot).map(p => h("button.btn.small" + (r.mode === "admin" && r.admin === p.id ? "" : ".ghost"), { onclick: () => setAdmin(p.id) }, C(p.name))))) : null;
    return [h("section.card.center", st.joined ? h("h2", T("Waiting for the start …")) : h("p", T("Play along on this device?")),
      st.joined ? h("p.muted.small", T("One device per team – everybody joins on their own device.")) : h("button.btn.big", { onclick: () => act0("join") }, "🙋 ", T("Join")),
      h("div.dm-seats", ...st.players.map(p => h("div.dm-seat" + (p.id === myId ? ".dm-me" : ""), seatIcon(p, 30), C(p.name, "strong.small.dm-name"))), ...free),
      h("p.small", "🏁 ", sjFill(T("Permit with {0} stamps"), st.target), adm ? [" · 🏛️ ", sjFill(T("Administration: {0}"), adm)] : null),
      st.coins_on ? h("p.small", "🪙 ", sjFill(T("Coins for places 1 / 2 / 3: {0}"), sjCoins(st.rewards))) : null, chooser),
      host ? h("div.row.center.host-bar", h("button.btn", { onclick: begin }, "▶ ", T("Start"))) : null];
  }
  async function act0(path) { try { st = await api("community/stempeljagd/" + path, { method: "POST", body: {} }); } catch (e) { toast(e.message, "bad"); } draw(true); }
  async function setAdmin(who_) { try { st = await api("community/stempeljagd/admin", { method: "POST", body: { who: who_ } }); } catch (e) { toast(e.message, "bad"); } draw(true); }
  async function begin() {
    if (busy) return;
    busy = true;
    try { const r = await beginGame("community/stempeljagd/begin", st.players); if (r) st = r; } catch (e) { toast(e.message, "bad"); }
    finally { busy = false; draw(true); }
  }

  function seats() {
    return h("div.sj-seats", ...st.players.map(p => {
      const n = (p.stamps || []).length, pr = SJ_PROJECTS[p.project];
      return h("div.sj-seat" + (st.actor === p.id ? ".turn" : "") + (p.id === myId ? ".me" : ""), { style: { "--sc": color(p.id) } },
        seatIcon(p, 22),
        h("div.sj-sinfo", C(p.name, "strong.small.sj-sname"),
          p.admin ? h("span.sj-stat", "🏛️ ", T("Administration"))
            : h("span.sj-stat", pr ? pr[0] + " " : "", h("b", n + "/" + st.target), " 🔖", p.skip ? " 🍽️" : "", p.sent_to ? " ↪️" + (SJ_DESK[p.sent_to][1] || "") : "", p.fines ? " 🟥" + p.fines : "")));
    }));
  }

  function projectPick() {
    const mineP = player(myId).project, taken = new Set(st.projects_taken || []);
    return h("section.card.sj-projects", h("h2", "🏗️ ", T("Which project do you want approved?")),
      mineP ? h("p.muted", sjFill(T("Your project: {0}"), sjTr(SJ_PROJECTS[mineP][1])), " – ", T("waiting for the other teams …")) : null,
      h("div.sj-pgrid", ...Object.entries(SJ_PROJECTS).map(([k, [ic, name]]) => h("button.sj-pbtn" + (mineP === k ? ".on" : ""),
        { disabled: !!mineP || (taken.has(k) && mineP !== k) || !!player(myId).admin, onclick: () => act("project", { key: k }) }, h("span.sj-pic", ic), h("span.small", name)))),
      isHost() ? h("p.small.muted", T("Who leads can go on: the other teams get a project at random (☰).")) : null);
  }

  // the town hall: the roof with the display board, the counters, the basement
  function hall() {
    const mine = st.mine || {}, allowed = new Set(st.my_turn && st.stage === "go" ? mine.allowed || [] : []);
    const d = st.display;
    const at = {};
    for (const p of st.players) if (!p.admin && (p.held || p.sent_to)) (at[p.held || p.sent_to] = at[p.held || p.sent_to] || []).push(p);
    const cur = st.cur || {};
    if (cur.counter && st.turn) (at[cur.counter] = at[cur.counter] || []).push(player(st.turn));
    const room = c => {
      const [ic, num, , clerk] = SJ_DESK[c], sc = (st.scenes || {})[c], why = (st.closed || {})[c];
      const desk = ["info", "building", "green", "slow"].includes(c);
      const q = desk && sc && sc.kind === "queue" && !why;
      const stat = why === "hours" ? sjTr(T("Tue + 🌑 only")) : why === "lunch" ? "🍽️ " + sjTr(T("Lunch break")) : why === "admin" ? "🔒 " + sjTr(T("closed")) :
        c === "slow" ? (st.meets ? "🔔 " + sjTr(T("meets today")) : sjFill(T("meets in {0}"), st.meets_in)) : null;
      return h("button.sj-room" + (desk ? ".desk" : "") + "." + c + (why ? ".shut" : "") + (q ? ".queue" : "") + (allowed.has(c) ? ".go" : ""),
        { type: "button", disabled: !allowed.has(c), onclick: () => act("go", { counter: c }), title: sjDeskName(c) },
        num ? h("span.sj-num", num) : null,
        h("span.sj-ric", ic), h("span.sj-rname", sjDeskName(c)),
        h("span.sj-clerk", clerk, sc && desk ? h("i", SJ_MOODS[sc.mood][0]) : null),
        q ? h("span.sj-q", "🧍".repeat(Math.min(4, Math.ceil(sc.queue / 6))), h("small", "×" + sc.queue)) : null,
        stat ? h("span.sj-rstat", stat) : null,
        h("span.sj-tokens", ...(at[c] || []).map(p => h("i.sj-tok", { style: { background: color(p.id) } }))),
        why ? h("span.sj-shutter") : null);
    };
    const ev = st.event && SJ_EVENTS[st.event];
    return h("div.sj-hall",
      h("div.sj-roof", h("span.sj-town", "🏛️ ", sjFill(T("Town hall of {0}"), sjTown())),
        h("div.sj-board", { title: sjTr(T("Now serving")) }, h("small", T("Now serving")), " ", h("b", d ? String(d.n).padStart(3, "0") : "---"), " → ", d ? sjDeskShort(d.c) : "…")),
      ev ? h("div.sj-event", ev[0], " ", sjTr(ev[1])) : null,
      h("div.sj-floors", room("info"), room("building"), room("green"), room("slow"), room("coffee"), room("archive")));
  }

  // ---------- the panel: what to do now (or what the others do)
  function cardBox(cur) {
    if (!cur || !cur.card) return null;
    return h("div.sj-card", h("span.sj-cardic", SJ_DESK[cur.counter] ? SJ_DESK[cur.counter][3] : "📄"), h("span", sjTr(SJ_CARDS[cur.card] || "")));
  }
  function resultText(cur, pid) {
    if (!cur) return null;
    const r = cur.result;
    const m = {
      stamp: "✅ " + sjTr(T("Stamp!")), stamp2: "✅✅ " + sjTr(T("Two stamps!")),
      refer: "↪️ " + sjFill(T("Referred to {0}."), sjDeskShort((player(pid).sent_to) || "info")),
      doc_ok: "📄 " + sjTr(T("The document is in the folder – stamp!")), folder: "📎 " + sjTr(T("The complete folder saves the day – stamp!")),
      missing: "❓ " + sjFill(T("Something is missing: {0}. Get it in the archive."), sjTr(SJ_DOCS[player(pid).todo] || "")),
      lunch: "🍽️ " + sjTr(T("The shutter comes down – the next turn is lunch.")), grumpy: "😠 " + sjTr(T("Nothing happens. Grumpily.")),
      holiday: "🏖️ " + sjTr(T("Nothing happens. Everybody is on holiday.")), nothing: "🤷 " + sjTr(T("Nothing happens.")),
      pile: "🐌 " + sjTr(T("On the pile – the commission decides at its next meeting.")),
      trick: "🎁 " + (cur.trick ? sjFill(T("A trick card: {0}"), SJ_TRICKS[cur.trick][0] + " " + sjTr(SJ_TRICKS[cur.trick][1])) : sjTr(T("Your hand is full."))),
      tree_yes: "🌳 " + sjTr(T("The tree rustles: yes! Stamp!")), tree_no: "🌳 " + sjTr(T("The tree says nothing. Come back when it has decided.")),
      mini_ok: "🏆 " + sjTr(T("Well done – stamp!")), mini_no: "🙈 " + sjTr(T("Not quite – no stamp this time.")),
      handed: "📄 " + sjFill(T("Finally complete: {0} handed in – stamp!"), sjTr(SJ_DOCS[cur.doc] || "")),
      no_audience: "🚪 " + sjTr((SJ_ARGS[cur.arg] || [, , T("«Please come back another day.»")])[2]),
      held: "⏳ " + sjTr(T("The display does not move – the clerks are chatting. Your place is kept for your next turn.")),
      caught: "🚨 " + sjTr((SJ_CHEATS[cur.how] || [, , ""])[2]),
      coffee: "☕ " + (cur.rumour ? sjFill(SJ_RUMOURS[cur.rumour], cur.info ?? "") : "") + (cur.trick ? " · " + SJ_TRICKS[cur.trick][0] : ""),
      doc: "🗄️ " + sjFill(T("Found in the archive: {0}"), sjTr(SJ_DOCS[cur.doc] || "")),
      preform_no: "📝 " + sjTr(T("The form for the form was not filled in. Try again another time.")),
      form_no: "📝 " + sjTr(T("The administration's form was not filled in – the turn is over.")),
      gift: "💌 " + sjTr(T("The small gift worked: two stamps! (Lucky this time.)")),
      inspector: "🕵️ " + sjTr(T("The order inspector! A fine – and back to counter 1.")),
      friendly: "🗣️ " + sjTr(T("The grumpy clerk melts at so much friendliness – stamp!")),
      objection: cur.ok ? "⚖️ " + sjFill(T("{0} defended the project."), who(cur.to)) + (cur.how === "compromise" ? " " + sjTr(SJ_PROJECTS[player(cur.to).project][3]) : "")
        : "⚖️ " + sjFill(T("The objection succeeded: {0} loses a stamp."), who(cur.to)),
    }[r];
    return m ? h("p.sj-result", m) : null;
  }
  function tricksRow(clickable) {
    const mine = st.mine || {};
    const list = [...(mine.tricks || []).map(k => [k, 1]), ...(mine.mayor ? [["mayor", 1]] : [])];
    const counts = {};
    for (const [k] of list) counts[k] = (counts[k] || 0) + 1;
    return h("div.sj-tricks", ...Object.keys(counts).map(k => {
      const [ic, name, desc] = SJ_TRICKS[k], active = clickable && ["gift", "objection", "mayor"].includes(k);
      return h("button.sj-trick" + (active ? ".act" : ""), { type: "button", title: sjTr(name) + ": " + sjTr(desc),
        onclick: () => active ? playTrick(k) : toast(ic + " " + sjTr(name) + ": " + sjTr(desc)) }, ic, counts[k] > 1 ? h("small", "×" + counts[k]) : null);
    }), (mine.folder || []).length ? h("span.sj-folder", { title: (mine.folder || []).map(d => sjTr(SJ_DOCS[d])).join(", ") }, "🗂️", h("small", (mine.folder || []).length)) : null);
  }
  async function playTrick(k) {
    if (k === "objection") {
      const targets = st.players.filter(p => !p.admin && p.id !== myId && (p.stamps || []).length);
      if (!targets.length) return toast(sjTr(T("No other team has a stamp yet.")));
      const m = modal(h("div.form.center", h("h2", "⚖️ ", T("Objection against …")),
        ...targets.map(p => h("button.btn.sj-obj", { onclick: () => { m.close(); act("play", { trick: k, target: p.id }); } },
          C(p.name), " – ", SJ_PROJECTS[p.project][0], " ", sjTr(SJ_PROJECTS[p.project][2]))),
        h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel"))));
      return;
    }
    const [ic, name, desc] = SJ_TRICKS[k];
    if (!(await confirmDialog(ic + " " + sjTr(name) + "\n" + sjTr(desc)))) return;
    act("play", { trick: k });
  }
  function panel() {
    const cur = st.cur || {}, mine = st.mine || {}, me_ = player(myId);
    const actorName = who(st.actor), stage = st.stage;
    const box_ = (...xs) => h("section.card.sj-panel" + (st.my_turn ? ".turn" : ""), { style: { "--sc": color(st.actor) } }, ...xs);
    if (!st.my_turn) {
      let msg = sjFill(T("{0} is playing …"), actorName);
      if (stage === "objection" && st.obj) msg = sjFill(T("{0} defends against an objection …"), actorName);
      else if (stage === "admin") msg = sjFill(T("The administration ({0}) is thinking …"), actorName);
      else if (cur.counter) msg = sjFill(T("{0} is at {1}."), actorName, sjDeskShort(cur.counter));
      return box_(h("div.sj-msg", h("span.muted", msg)), cardBox(cur), resultText(cur, st.turn), me_.admin ? null : tricksRow(false));
    }
    const say = (clerk, text) => h("div.sj-say", h("span.sj-sayic", clerk), h("span.sj-bubble", text));
    const clerk = SJ_DESK[cur.counter] ? SJ_DESK[cur.counter][3] : "🧑‍💼";
    const mood = cur.mood && SJ_MOODS[cur.mood];
    if (stage === "go") {
      const p = me_;
      let hint = sjTr(T("Your turn – tap a counter in the town hall."));
      if (p.held) hint = sjFill(T("Your place in the queue at {0} is kept – go there."), sjDeskShort(p.held));
      else if (p.sent_to && (mine.allowed || []).length === 1) hint = sjFill(T("You were sent to {0}."), sjDeskShort(p.sent_to));
      return box_(h("strong.sj-turnmsg", hint),
        p.todo ? h("p.small.sj-todo", "❓ ", sjFill(T("Missing: {0}"), sjTr(SJ_DOCS[p.todo]))) : null,
        tricksRow(true), h("p.small.muted.sj-tip", T("Tap ⚖️ 💌 📣 to play them; the others work by themselves.")));
    }
    if (stage === "appt") {
      const has = (mine.tricks || []).includes("appointment");
      return box_(say(clerk, sjTr(T("«Do you have an appointment?»"))),
        h("div.row.wrap.sj-btns", h("button.btn", { disabled: !has, onclick: () => act("appt", { yes: true }) }, "📅 ", T("Yes")),
          h("button.btn.ghost", { onclick: () => act("appt", { yes: false }) }, T("No"))),
        has ? null : h("p.small.muted", T("Without an appointment card you can only say «No».")));
    }
    if (stage === "argue") {
      const tricks = mine.tricks || [];
      return box_(say(clerk, sjTr(T("«We are fully booked for the next 9 months.»"))),
        h("p.small.sj-empty", "🪑🪑🪑🪑 ", T("(The waiting room is completely empty.)")),
        mood ? h("p.small.muted", sjFill(T("The clerk seems {0}."), mood[0] + " " + sjTr(mood[1]))) : null,
        h("div.sj-args", ...Object.entries(SJ_ARGS).filter(([k]) => !["croissant", "connections"].includes(k) || tricks.includes(k))
          .map(([k, [ic, label]]) => h("button.btn.small.sj-arg", { onclick: () => act("argue", { key: k }) }, ic, " ", label))));
    }
    if (stage === "queue") {
      const sc = (st.scenes || {})[cur.counter] || {};
      return box_(h("p.sj-qline", "🧍".repeat(6), " ", sjFill(T("{0} people are waiting. The display has been stuck at {1} for ages – the clerks are chatting."), cur.queue, String(sc.shown || 1).padStart(3, "0"))),
        h("div.sj-args", h("button.btn.small", { onclick: () => act("queue", { key: "wait" }) }, "⏳ ", T("Wait patiently")),
          ...(cur.cheats || []).map(k => h("button.btn.small.ghost.sj-arg", { onclick: () => act("queue", { key: k }) }, SJ_CHEATS[k][0], " ", SJ_CHEATS[k][1]))));
    }
    if (stage === "card") {
      return box_(cardBox(cur), h("div.row.wrap.sj-btns", h("button.btn", { onclick: () => act("react", { use: true }) }, "🤝 ", T("Use connections")),
        h("button.btn.ghost", { onclick: () => act("react", { use: false }) }, T("Accept the referral"))));
    }
    if (stage === "objection") {
      const o = st.obj || {}, pr = SJ_PROJECTS[me_.project] || ["", "", ""];
      return box_(h("p.sj-qline", "⚖️ ", sjFill(T("{0} objects: «{1}»"), who(o.from), sjTr(pr[2]))),
        h("div.sj-args", h("button.btn.small", { disabled: !(mine.folder || []).length, onclick: () => act("defend", { key: "report" }) }, "📋 ", T("Expert report (a document)")),
          h("button.btn.small", { onclick: () => act("defend", { key: "signatures" }) }, "✍️ ", T("Neighbours' signatures")),
          h("button.btn.small", { onclick: () => act("defend", { key: "compromise" }) }, "🤝 ", T("Compromise:"), " ", sjTr(pr[3]))));
    }
    if (stage === "admin") return box_(adminPanel());
    if (stage === "mini") return box_(h("p.muted", T("Fill it in …")));
    // done
    return box_(cardBox(cur), resultText(cur, st.turn), h("div.row.center", h("button.btn.sj-end", { onclick: () => act("end_turn") }, "✓ ", T("End turn"))));
  }
  let adminPick = null;
  function adminPanel() {
    const hand = (st.mine || {}).hand || [];
    const builders = st.players.filter(p => !p.admin);
    return h("div.sj-admin", h("strong.sj-turnmsg", "🏛️ ", T("The administration's turn: play a card on a team – or open / close a counter.")),
      h("div.sj-hand", ...hand.map((k, i) => h("button.sj-acard" + (adminPick === i ? ".on" : ""), { title: sjTr(SJ_ADMIN[k][2]), onclick: () => { adminPick = i; draw(true); } },
        h("span", SJ_ADMIN[k][0]), h("small", SJ_ADMIN[k][1])))),
      adminPick != null && hand[adminPick] ? h("div.row.wrap.sj-btns", ...builders.map(p => h("button.btn.small", { onclick: () => { const i = adminPick; adminPick = null; act("admin_card", { idx: i, target: p.id }); } },
        "🎯 ", C(p.name)))) : h("p.small.muted", T("Choose a card first.")),
      h("div.row.wrap.sj-btns", ...["info", "building", "green", "slow", "archive"].map(c => h("button.btn.small.ghost", { onclick: () => act("admin_toggle", { counter: c }) },
        (st.closed || {})[c] === "admin" ? "🔓 " : "🔒 ", SJ_DESK[c][1] || SJ_DESK[c][0]))));
  }

  // ---------- mini-games (the server checks the result)
  function miniGame() {
    const cur = st.cur || {}, m = cur.mini;
    if (!(st.stage === "mini" && st.my_turn && m)) { if (miniKey) closeOverlay(); return; }
    const key = st.game + ":" + m.start;
    if (key === miniKey) return;
    if (overlay && overlay.classList.contains("sj-call")) { setTimeout(() => draw(true), 2700); return; }   // the phone call first
    closeOverlay();
    miniKey = key;
    const send = data => { const k = miniKey; closeOverlay(); miniKey = k; act("mini", data); };
    const left = () => m.until - (Date.now() / 1000 + skew);
    const bar = h("div.sj-timer", h("i"));
    const tickBar = () => { const f = Math.max(0, left() / (m.until - m.start)); const i = bar.firstChild; if (i) i.style.width = (f * 100) + "%"; return f; };
    let body;
    if (m.game === "form") {
      let done = 0;
      const boxes = m.boxes.map((k, i) => {
        let hops = 0;
        const b = h("button.sj-box", { type: "button", style: { left: (8 + i * 4) + "%", top: (6 + i * 30) + "%" }, onclick: () => {
          if (b.classList.contains("ok")) return;
          if (hops < 1 + (i % 2)) { hops++; b.style.left = (5 + Math.random() * 45) + "%"; b.style.top = (Math.random() * 70) + "%"; return; }   // it slides away
          b.classList.add("ok"); done++;
          try { Sound.play("tap"); } catch {}
          if (done >= m.boxes.length) send({ ticked: done });
        } }, h("span.sj-chk"), h("span.small", sjTr(SJ_BOXES[k])));
        return b;
      });
      body = [h("h2", "📝 ", T("Form 08/15-Z: tick all the boxes!")), h("p.small.muted", T("Careful – the boxes slide away.")), h("div.sj-formfield", ...boxes)];
      const t = setInterval(() => { if (!overlay || miniKey !== key) return clearInterval(t); if (tickBar() <= 0) { clearInterval(t); send({ ticked: done }); } }, 200);
    } else if (m.game === "stamp") {
      const mark = h("i.sj-mark"), zone = h("i.sj-zone", { style: { left: ((m.center - m.width) * 100) + "%", width: (m.width * 200) + "%" } });
      const track = h("div.sj-track", zone, mark);
      const loop = () => {
        if (!overlay || miniKey !== key) return;
        const x = ((Date.now() / 1000 + skew - m.start) / m.period) % 2, pos = x <= 1 ? x : 2 - x;
        mark.style.left = (pos * 100) + "%";
        if (tickBar() <= 0) return send({});
        requestAnimationFrame(loop);
      };
      body = [h("h2", "🔖 ", T("Stamp it – right in the box!")), track,
        h("button.btn.big.sj-stampbtn", { onclick: () => { try { Sound.play("tap"); if (navigator.vibrate) navigator.vibrate(30); } catch {} send({}); } }, "🔖 ", T("STAMP!"))];
      requestAnimationFrame(loop);
    } else {
      const sentence = sjFill(T("«According to article {0}, paragraph {1}, item {2}, sub-item {3}, the application must be submitted before it is submitted.»"),
        m.article, m.paragraph, sjTr(SJ_ITEMS[m.item] || "?"), m.extra);
      const q = h("div.sj-speakq");
      body = [h("h2", "🗣️ ", T("Bureaucratic speak")), h("p.sj-bubble.sj-law", sentence), q];
      setTimeout(() => {
        if (!overlay || miniKey !== key) return;
        overlay.querySelector(".sj-law").classList.add("gone");
        q.replaceChildren(h("p", h("strong", T("Which item was it?"))), h("div.sj-args", ...m.options.map((o, i) => h("button.btn", { onclick: () => send({ answer: i }) }, sjTr(SJ_ITEMS[o])))));
      }, 4500);
      const t = setInterval(() => { if (!overlay || miniKey !== key) return clearInterval(t); if (tickBar() <= 0) { clearInterval(t); send({ answer: 9 }); } }, 200);
    }
    overlay = h("div.sj-overlay", h("div.sj-mini.card", ...body, bar));
    document.body.append(overlay);
    tickBar();
  }

  // ---------- the end: the permit certificate and the funniest moments
  function moments() {
    const lines = (st.moments || []).slice(0, 4).map(m => {
      const n = who(m.p);
      const t = { ref_to: [T("{0} was sent to counter {1} {2} times."), n, SJ_DESK[m.c] ? SJ_DESK[m.c][1] || "?" : "?", m.n],
        pingpong: [T("{0} played ping-pong between the counters {1} times."), n, m.n], booked: [T("{0} heard «fully booked for 9 months» {1} times."), n, m.n],
        lunch: m.n === 1 ? [T("{0} had a lunch break."), n] : [T("{0} watched the shutter come down {1} times."), n, m.n], caught: m.n === 1 ? [T("{0} was caught by the order inspector."), n] : [T("{0} was caught by the order inspector {1} times."), n, m.n],
        cheats_caught: m.n === 1 ? [T("{0} was caught jumping the queue."), n] : [T("{0} was caught jumping the queue {1} times."), n, m.n], tree_no: m.n === 1 ? [T("{0} waited for the tree to decide."), n] : [T("{0} waited {1} times for the tree to decide."), n, m.n],
        objections_won: m.n === 1 ? [T("{0} won an objection."), n] : [T("{0} won {1} objections."), n, m.n], postponed: [T("The application of {0} was postponed {1} times."), n, m.n],
        computer_no: m.n === 1 ? [T("The computer said no to {0}."), n] : [T("The computer said no to {0} {1} times."), n, m.n], missing: [T("Something was missing for {0} {1} times."), n, m.n],
        croissants: m.n === 1 ? [T("{0} handed out croissants."), n] : [T("{0} handed out croissants {1} times."), n, m.n], calls: [T("The clerks had to phone a colleague for {0} {1} times."), n, m.n],
        friendly: m.n === 1 ? [T("{0} melted a grumpy clerk with friendliness."), n] : [T("{0} melted {1} grumpy clerks with friendliness."), n, m.n] }[m.k];
      return t ? h("li", sjFill(...t)) : null;
    }).filter(Boolean);
    return lines.length ? h("div.sj-moments", h("strong", "😂 ", T("The funniest moments")), h("ul.small", ...lines)) : null;
  }
  function certificate() {
    const ranked = [...st.players].sort((a, b) => (a.place || 99) - (b.place || 99));
    const w = st.winner ? player(st.winner) : null;
    if (player(myId).place === 1 && st.complete && !cheered) { cheered = true; confetti(); try { Sound.play("done"); } catch {} }
    const medal = n => ["🥇", "🥈", "🥉"][n - 1] || n + ".";
    const pr = w && SJ_PROJECTS[w.project];
    const stampsOf = p => (p.stamps || []).map((s, i) => h("span.sj-stamp", { style: { transform: `rotate(${((i * 37) % 30) - 15}deg)` } },
      h("b", SJ_DESK[s.o] ? SJ_DESK[s.o][0] : s.o === "mayor" ? "📣" : s.o === "gift" ? "💌" : "🔖"), h("small", sjFill(T("Day {0}"), s.r))));
    const doc = w ? h("div.sj-cert", h("div.sj-certhead", "🏛️ ", sjFill(T("Town hall of {0}"), sjTown())), h("h2", T("BUILDING PERMIT")),
      h("p", sjTr(T("is hereby granted to")), " ", C(w.name, "strong"), " ", sjTr(T("for")), h("br"), h("b.sj-certproj", pr ? pr[0] + " " + sjTr(pr[1]) : "")),
      w.compromise ? h("p.small", "✳️ ", sjTr(T("Condition:")), " ", sjTr(SJ_PROJECTS[w.compromise][3])) : null,
      h("div.sj-stamps", ...stampsOf(w)), h("p.small.sj-sign", "✒️ ", T("The Mayor (probably)")))
      : h("div.sj-cert.denied", h("div.sj-certhead", "🏛️ ", sjFill(T("Town hall of {0}"), sjTown())),
        h("h2", st.admin_won ? T("APPLICATIONS PENDING") : T("NO PERMIT YET")), h("span.sj-denied", st.admin_won ? T("The administration wins!") : T("Ended early")));
    return h("section.card.center.sj-result", doc,
      h("ol.pk-rank", ...ranked.map(p => h("li" + (p.id === myId ? ".hw-me" : ""), h("span.pj-medal", medal(p.place)), seatIcon(p, 26), C(p.name, "strong.grow"),
        h("span", p.admin ? "🏛️" : (p.stamps || []).length + " 🔖"), p.coins ? h("b.pj-plus", "+" + p.coins + " 🪙") : null))),
      moments(),
      st.complete ? null : h("p.small.muted", T("The game was ended early – ranked as it stood, no coins.")),
      st.coins_on ? null : h("p.small.muted", st.solo ? T("Alone against bots there are no coins.") : T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots.")),
      h("div.row.center", h("button.btn", { onclick: back }, T("Back"))));
  }
  poll();
}

async function stempeljagdView() {
  const box = h("div.sj-live");
  screen("games", box);
  stempeljagdLive(box, S.profile, () => go("games"));
}

async function stempeljagdFamilyCard() {
  const c = S.me && S.me.community, g = c && c.stempeljagd;
  return h("section.card.quiz-card", h("h2", SJ_ICON, " ", sjName()),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("stempeljagd") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("Collect every stamp for your building project in a wonderfully complicated town hall – despite queues, referrals and lunch breaks. Places 1 to 3 win coins at the family table.")),
         gameStartRow(botsOn("stempeljagd") ? () => stempeljagdStartDialog(true, () => go("stempeljagd")) : null, () => stempeljagdStartDialog(false, () => go("stempeljagd")))]);
}
