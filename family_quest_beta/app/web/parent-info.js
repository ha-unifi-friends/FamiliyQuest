// ---------------------------------------------------------------- ⓘ in the parent area
// Every box (right of its title), every page (right of the heading) and every pop-up (top right) gets an info button
// that describes it. The headings are found by their text (English or translated) – no change to the views needed.
const PARENT_INFO = {
  [T("Overview")]: T("The start page of the parent area: open approvals, today's weather of each child, the family goal and one card per child with XP, learning time, weak spots and the balance. Add children and parents at the top right."),
  [T("Calendar")]: T("The family calendar: events, FamilyTime and OfflineTime. Switch between list, day, week, month and year; tap a day to add an event. Below: holiday templates, calendar files and calendars from Home Assistant."),
  [T("Packs")]: T("Learning packs: switch them on per child, edit them, export them or check drafts. «Import» adds new packs from a file, a link or a photo."),
  [T("Chores")]: T("The chore plan: chores with points, how often they come and who does them (fixed or rotating). Duties are expected, bonus chores bring extra points. Children tick them off, you confirm."),
  [T("Community")]: T("Everything the family does together: family council, polls, Wichteln, family quiz and the games. Children can take part, start games and open topics too."),
  [T("Rewards")]: T("Accounts and the shop: what children can buy with their points (vouchers, internet minutes, avatar items, Home Assistant scripts) and the rules how many points an activity gives."),
  [T("Goals")]: T("Weekly goals for a child (e.g. 3 learning days) and the family goal everybody works on together. Reached goals give a bonus."),
  [T("Dashboard")]: T("The kiosk dashboard for a tablet on the wall: what it shows (chores, calendar, weather, points) and the link to open it."),
  [T("Settings")]: T("General settings: what children see in the family comparison, sound, reminders, levels, games, season designs, weather, logins, network access, translations, backup and the Family Planer."),
  [T("Import")]: T("Add learning packs: a YAML, JSON, ZIP, CSV or Excel file, a link, or (with an AI in Home Assistant) a photo or PDF of a word list. Everything becomes a draft you check before children see it."),
  [T("Waiting for your approval")]: T("Children bought something in the shop that needs your OK. Approve it (the points are booked) or decline it (the points go back)."),
  [T("Chores to confirm")]: T("Chores children ticked off that need your confirmation before the points are booked. Send one back if it was not done properly."),
  [T("Weather of the day")]: T("The behaviour weather: give each child its weather for today. Sunny gives a bonus, a thunderstorm a malus – only the child sees its own weather. Everybody is back at the default at the reset time."),
  [T("Weather settings")]: T("The weather levels with icon, name and points, which account the points go to, the default weather and when every day it resets."),
  [T("Family goal")]: T("A goal the whole family reaches together, e.g. 50 lessons this month. Everybody's progress counts; reaching it can unlock a reward."),
  [T("Parents")]: T("The parent profiles: each parent logs in with the Home Assistant user or a PIN, confirms chores and rewards and can learn along."),
  [T("Archived profiles")]: T("Profiles that were removed with «archive»: hidden, but their history stays. Restore them here or delete them for good."),
  [T("Failed logins (30 days)")]: T("Wrong PINs of the last 30 days with time and device – to notice when somebody tries to guess a PIN."),
  [T("Family council")]: T("Everybody can bring up a question, collect ideas and then vote secretly. You choose the majority (simple, absolute, unanimous) and whether the winner needs a parent's and a child's vote."),
  [T("Polls")]: T("A quick question to the family with 2 to 12 answers – one or several answers, anonymous or with names, optionally with a closing time. Everybody sees the result after answering."),
  [T("Wichteln")]: T("Secret gift giving: enter the occasion and an optional date, choose who takes part and the rules. The app draws at random who gives to whom; everybody only sees their own. With a date everybody gets a to-do in the planner."),
  [T("Family quiz")]: T("Your own quizzes and the templates: start a quiz, everybody plays on their own device, you show the next question. Filter by not played yet / played; «New quiz» makes one or takes a template."),
  [T("Running quiz")]: T("The quiz that is running right now: who joined, the current question and the ranking. You lead – show the next question or end the game."),
  [T("Bingo")]: T("Bingo with the whole family: everybody gets a card, the balls come by themselves, players mark their numbers and shout «Bingo!». Start a game or open it in the app."),
  [T("Guess the song")]: T("A speaker of Home Assistant plays its playlist; whoever knows the song buzzes, the others judge. Volume, countdown, who shows the solution and the sounds are set when starting."),
  [T("Tschau Sepp")]: T("The Swiss card game: get rid of your cards first, say «Tschau» and «Sepp». Open a family table or play alone against bots; rules and card back are chosen at the start."),
  [T("Kartenkarussell")]: T("A colourful card game like the classic with colours and numbers: special cards, draw cards that add up, your own bots. Family table or alone against bots."),
  [T("Domino")]: T("Domino with double-6 or double-9 tiles, simple or Cuban rules, in teams. Tap a tile to play, choose the end, pass when nothing fits. The score sheet counts every round; Pollona = won with the others at 0."),
  [T("Paarjagd")]: T("The live pairs game: everybody turns cards on their own device, a pair scores and you go again. Choose the cards (emoji or your photo sets), the number of pairs, bots and the card back. Below, set the coins for places 1, 2 and 3 – they are only paid at a family table with at least two people of the family, never alone against bots, to guests or to bots."),
  [T("Wer bin ich?")]: T("The live guessing game: everybody gets a secret character of the chosen category and sees the characters of the others. On your turn ask a yes/no question, guess or give up – the others answer on their devices. Only people play (guests via QR code), no bots. Below, set the coins for places 1, 2 and 3 – only paid at a table with at least two people of the family, never to guests."),
  [T("Kartenlauf")]: T("The race board game with cards: everybody brings four marbles around the board and home – cards say how far, the 7 is split, the jack swaps, kicked marbles go back to the kennel. 2 to 4 players, in teams of two with 4 (partners opposite), bots fill free seats. Below, set the coins for places 1, 2 and 3 – a winning team gets place 1 for both; only paid at a family table with at least two people of the family, never alone against bots, to guests or to bots."),
  [T("Stadt-Land-Fluss")]: T("The word game live: who opens the table chooses 3 to 8 categories (or own ones), the rounds, the time per round (or until somebody calls «Stopp!») and whether «Stopp!» gives the others 10 more seconds. Everybody writes on their own device, then all answers are shown – the others can reject an answer with 👎, who leads can decide. 20 / 10 / 5 points per answer. Only people play (guests via QR code), no bots. Below, set the coins for places 1, 2 and 3 – only paid at a table with at least two people of the family, never to guests."),
  [T("Zeichnen & Raten")]: T("The drawing game live: who opens the table chooses the words (animals, jobs, food, things at home, sports or mixed), how often everybody draws (1 to 3 times), the time to draw (60 / 80 / 120 seconds) and whether letters are shown as hints. The drawer picks one of 3 words and draws it on their device; the others see the drawing live and type guesses – the faster, the more points, the drawer gets 10 points per player who found it. Only people play (guests via QR code), no bots. Below, set the coins for places 1, 2 and 3 – only paid at a table with at least two people of the family, never to guests."),
  [T("Fünf Würfel")]: T("The dice game with five dice live: 13 rounds, in every round everybody rolls on their own device at the same time – up to 3 rolls, tap dice to hold them – and fills one box of the score sheet (or crosses one out). 1 to 6 players, alone or with bots (easy / normal / hard), guests via QR code. 35 bonus with 63 points in the upper section; optional +50 for every further «Fünfling». Below, set the coins for places 1, 2 and 3 – only paid for a game played to the end at a family table with at least two people of the family, never alone against bots, to guests or to bots."),
  [T("Heimwärts")]: T("The classic race board game live: roll the die (on the server), bring your 4 pieces from the yard around the board and into your home – a 6 brings a piece out and rolls again, landing on another piece sends it back to its yard. 2 to 4 players, alone against 1 to 3 bots (easy / normal / hard) or at the family table with optional bots, guests via QR code. Rule options: benches (Eile mit Weile – safe fields nobody may pass), the exact number into the home, play on for places 2 and 3. Below, set the coins for places 1, 2 and 3 – only paid for a game played to the end at a family table with at least two people of the family, never alone against bots, to guests or to bots."),
  [T("Jump")]: T("The jumping race live: everybody has their own lane, the obstacles come from the left – tap the big button to jump. All lanes get the same obstacles, it gets faster and later there are double and long ones. Everybody has 1, 3 or 5 lives; who hits an obstacle loses one, the last one still running wins. 1 to 6 players at the family table (guests via QR code), or alone for a high score (the personal best is kept), optionally with practice bots (easy / normal / hard). Below, set the coins for places 1, 2 and 3 – only paid for a game played to the end at a family table with at least two people of the family, never alone, to guests or to bots."),
  [T("Verbotene Wörter")]: T("The explaining game live: one explains a word on their device without saying the 5 forbidden words, the others guess aloud. Who opens the table chooses the cards (easy for younger children, normal or mixed – about 370 German cards), the time per turn (30 to 120 seconds), how often everybody explains and whether «Skip» costs a point. With 4 or more players two teams play (the other team sees the card and can buzz), with 2 or 3 everybody plays for themselves. Only people play (guests via QR code), no bots. Below, set the coins for places 1, 2 and 3 – only paid at a table with at least two people of the family, never to guests."),
  [T("Jass")]: T("The Swiss card game Schieber live: 4 players in 2 teams (partners opposite), any mix of the family, guests and bots (easy / normal / hard). Who is on turn chooses Trumpf, Obenabe or Undeufe or pushes it to the partner; the server deals and checks every card (follow suit, no under-trumping, the Buur may be held back). Swiss or French cards, Weis and Stöck, multipliers, a game to 500–2500 points or a number of rounds. Below, set the coins for each person of the family in the winning team – only paid for a game played to the end at a family table with at least two people of the family, never alone against bots, to guests or to bots."),
  [T("Klatsch den Beat")]: T("The rhythm game live: every round the app plays a short beat (its own drum sounds), then everybody claps it back on their phone at the same time – a playhead runs over the dots of the pattern. The server judges every clap (perfect ±60 ms, good ±130 ms, extra claps cost points) and ranks everybody the same way; it gets faster from round to round (80 to 140 BPM) with syncopes and pauses, 5 to 8 rounds. A short calibration per device subtracts the sound delay. 1 to 8 players at the family table (guests via QR code), or alone for a personal best, optionally with practice bots (easy / normal / hard). Below, set the coins for places 1, 2 and 3 – only paid for a game played to the end at a family table with at least two people of the family, never alone, to guests or to bots."),
  [T("Werwölfe")]: T("The classic social deduction party game in one room, 5 to 12 players (family and guests via QR code): the app is the game master. Everybody gets a secret role on their phone – werewolves, villagers, seer, witch, hunter, Amor. At night only the active role acts on its phone, by day the village talks (timer) and votes on every phone. Who leads chooses the roles (or lets the app choose by the number of players), can move on when somebody is idle and end the game. Coins go to the family members on the winning side."),
  [T("Chess")]: T("Chess with the full rules (check, castling, en passant, promotion, draws by repetition, the 50-move rule and too little material): against a bot (easy: mostly random, normal: looks two moves ahead, hard: thinks deeper), against somebody of the family on two devices (an invitation, or an open seat for guests via QR code) or two people on one device. Optional clock of 5, 10 or 15 minutes per side. Every game can be paused – the clock stops – and continued later, also after a restart; several games per person. Who started a game or a parent deletes a paused game; «Running games» ends any game without a result. Below, set the coins for a win against the family, the hard bot and the normal bot (only after at least 10 own moves)."),
  [T("Dorfmarkt")]: T("The property-trading board game in a Swiss village, 2 to 6 players (family, guests via QR code, bots easy / normal / hard): roll two dice (on the server), buy shops and places, build market stands and a market hall with a whole colour group, collect rent, trade fields and Taler, mortgage when short. Default: after 30 rounds the richest wins – or a time limit, or classic until one is left. Who leads may pause the game; it is saved and survives a restart. Coins for places 1 to 3 only for a game played to the end at a family table with at least two people of the family."),
  [T("Texas Hold'em")]: T("Poker with play chips – everybody on their own device, or alone against bots. No real money; the chips start again every game."),
  [T("History")]: T("What a profile experienced: quiz places, council decisions, games won. Choose the profile to see its history."),
  [T("Games")]: T("Which games are switched on: for everybody, only for chosen children, or off. Parents can always play. The family council and polls stay open for everybody."),
  [T("Season designs")]: T("The animated scene in the header of the app: seasons, Halloween and Christmas switch themselves every year. Switch them on or off, move the dates or add your own designs (e.g. a birthday week)."),
  [T("Pairs game: photo sets")]: T("Your own photo sets for the pairs game and the Paarjagd (e.g. family members, holidays) – from Home Assistant Media or uploaded from this device. Every photo becomes a pair."),
  [T("Family crest")]: T("Your family crest – drawn from colours, pattern and symbol, or your own picture. It is shown on the card backs, on the dashboard and on posters."),
  [T("Log in with Home Assistant")]: T("Parents can log in with their Home Assistant user instead of a PIN. Choose whether the parent area may only be opened inside Home Assistant."),
  [T("Access from the network")]: T("Which networks may open the app directly (without Home Assistant): e.g. the home network yes, the guest network only for game guests."),
  [T("Backup & restore")]: T("Download everything (database, Planer data, pack pictures) as one file, or restore such a file. Make a backup before big changes."),
  [T("Shopping list (Bring!)")]: T("Connects the Family Quest shopping list with a todo list of Home Assistant, e.g. Bring!: items are synchronised both ways."),
  [T("One chore plan: the Planner")]: T("The Family Planer is built in: chores, to-dos, lists and awards. Here you open its settings and link its persons with the Family Quest profiles."),
  [T("Take over an existing Family Planer")]: T("If the Family Planer integration already runs in Home Assistant, take over its persons, chores and settings once."),
  [T("Templates: school and public holidays")]: T("Add the school and public holidays of a canton to the calendar with one click."),
  [T("Import a calendar file")]: T("Add events from an ICS or CSV file. Duplicates are marked; you choose which events to take."),
  [T("Calendars from Home Assistant")]: T("Show calendars of Home Assistant (read only) in the family calendar, e.g. the school or work calendar."),
  [T("This week")]: T("The chores of this week per day and child – what is done and what is still open."),
  [T("All chores")]: T("Every chore with its frequency, who does it, the points and whether it is a duty or a bonus. Tap one to change it."),
  [T("Levels")]: T("How many XP are needed for each level. Children see their level in the header."),
  [T("Family view")]: T("What children see when they compare themselves with the others, and whether the sound is on by default."),
  [T("Link for tablets and phones")]: T("The address and QR code to open the app on a tablet or phone in the home network."),
  [T("Link for the kiosk browser")]: T("The address of the dashboard for a wall tablet in kiosk mode."),
  [T("What the dashboard shows")]: T("Choose the tiles of the kiosk dashboard: chores, calendar, weather, points, family goal and more."),
  [T("To check")]: T("Imported packs that are drafts: check the cards and publish them – only then children see them."),
  [T("New event")]: T("A new calendar entry: title, all day or with times, icon and colour. FamilyTime is highlighted with a countdown; OfflineTime switches off the internet and / or the games for the chosen children."),
  [T("New chore")]: T("A chore with points, frequency (daily, weekdays, weekly, once) and who does it – fixed or rotating. Duty = expected, bonus = extra points."),
  [T("New poll")]: T("Ask a question with 2 to 12 answers. Choose one or several answers, anonymous or with names and an optional closing time."),
  [T("New topic")]: T("Bring up a question for the family council. Everybody can add ideas; then you start the vote."),
  [T("New Wichteln")]: T("Enter the occasion and an optional date, choose who takes part and the rules (parents not among each other, children not among each other). On «Draw» the pairs are drawn at random."),
  [T("New quiz")]: T("Make your own quiz or take one of the templates (filter by region). The quiz is then in the list and can be played."),
  [T("Edit quiz")]: T("Questions with 2 to 4 answers (the right one marked), estimation questions with a number, map questions or picture questions, and the time per question."),
  [T("Start bingo")]: T("The rules of the bingo: card size, how fast the balls come and what counts as bingo."),
  [T("Start the vote")]: T("Choose the majority the vote needs and whether the winner needs a parent's and a child's vote. Then everybody votes secretly."),
  [T("Book points")]: T("Book points to or from a child by hand, e.g. for a good deed – with a reason the child sees."),
  [T("Add account")]: T("A new points account (e.g. «Batzen» or «Screen minutes») with icon and name; children collect and spend in it."),
  [T("Weekly goal for a child")]: T("A goal for one week, e.g. learning on 4 days or 300 XP. Reached goals give the bonus you set."),
  [T("Remove profile")]: T("Archive (hidden, history kept, can be restored) or delete for good with all data. Type the name to confirm."),
  [T("Release notes")]: T("What is new in every version of Family Quest. «Check for updates» opens the add-ons page of Home Assistant."),
  [T("Invite guests")]: T("Guests (friends, grandparents) join a game with the QR code on their own phone – without a profile."),
  [T("Own texts and languages")]: T("Change texts of the app or add your own language (e.g. a family dialect) based on an existing one."),
  [T("Level packs")]: T("Level packs bundle several learning packs for a school level and semester. Switching one on for a child activates all its packs."),
  [T("Accounts")]: T("The point accounts of the family (e.g. coins, XP, internet minutes): name, icon and whether children can spend from it in the shop."),
  [T("Rules: which action gives how much on which account")]: T("What gives points: a right answer, a lesson, the daily goal, a chore … – how many points on which account and how many at most per day."),
  [T("Shop")]: T("What children can buy with their points: vouchers you fulfil, internet minutes, avatar items or a Home Assistant script. Rewards with approval wait for your OK."),
  [T("Current goals")]: T("All goals that are running now. 🎯 A learning goal is for one child: a whole pack up to a percentage, or one unit with a number of stars. 🤝 A family goal is collected by everybody together on one account, e.g. 2000 coins for a pizza evening. Below each goal: for whom and the target. ✕ deletes a goal; new ones with the buttons at the top right."),
  [T("Home Assistant")]: T("Reminders and push messages through Home Assistant: when children without the daily goal or with open chores are reminded, the notify service for approvals and whether learning coins also count as Family Planer points."),
  [T("About")]: T("The version of Family Quest and what is connected: Home Assistant, the built-in planner and the photo / PDF import."),
  [T("From a file")]: T("Choose or drop a file: YAML, JSON or ZIP packs, CSV or Excel tables (you assign the columns) or – with an AI in Home Assistant – a photo or PDF of a word list."),
  [T("Made with your AI")]: T("The template is a JSON file that describes itself to an AI: English instructions, a guide to every field and an example. JSON exports carry the same explanations, so an AI can also change, extend or translate existing content. The AI answers with a JSON file – upload it, it becomes a draft you check."),
  [T("From a link")]: T("Load a pack from an address in the internet (YAML, JSON or ZIP). It becomes a draft too."),
  [T("Format")]: T("An example of how a pack is written in YAML: subject, level, language and units with cards and exercises.")
};

const _infoNorm = s => String(s || "").replace(/ⓘ/g, "").replace(/^[^\p{L}\p{N}]+/u, "").replace(/\s+/g, " ").trim();
function infoKey(text) {
  const t = _infoNorm(text);
  if (!t) return null;
  for (const k of Object.keys(PARENT_INFO)) if (t === k || t === I18N.tr(k)) return k;
  return null;
}

function infoButton(key, title) {
  return h("button.info-btn", { type: "button", title: T("Info"), "aria-label": T("Info"), onclick: e => {
    e.preventDefault(); e.stopPropagation();
    const m = modal(h("div.info-modal", h("h2", "ⓘ ", C(_infoNorm(title))), h("p.info-text", T(PARENT_INFO[key])),
      h("div.row", h("button.btn", { onclick: () => m.close() }, T("Close")))));
  } }, "ⓘ");
}

function decorateInfo(root = document) {
  root.querySelectorAll(".page-head h1, section.card > h2, section.card > .sec-head > h2, .modal h2").forEach(el => {
    if (el.dataset.info || el.closest(".info-modal")) return;
    const key = infoKey(el.textContent);
    el.dataset.info = key ? "1" : "0";
    if (!key) return;
    const btn = infoButton(key, el.textContent);
    const box = el.closest(".modal");
    if (box && box.querySelector("h2") === el) { btn.classList.add("info-corner"); box.append(btn); }
    else el.append(btn);
  });
}

(() => {
  let pending = false;
  const run = () => { pending = false; try { decorateInfo(); } catch (e) { /* never break the page */ } };
  new MutationObserver(() => { if (!pending) { pending = true; setTimeout(run, 60); } }).observe(document.documentElement, { childList: true, subtree: true });
})();
