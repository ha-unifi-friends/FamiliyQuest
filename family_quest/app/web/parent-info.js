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
  [T("Import")]: T("Add learning packs: a YAML, JSON, ZIP, CSV or Excel file, a link, or (with an API key) a photo or PDF of a word list. Everything becomes a draft you check before children see it."),
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
  [T("Texas Hold'em")]: T("Poker with play chips – everybody on their own device, or alone against bots. No real money; the chips start again every game."),
  [T("History")]: T("What a profile experienced: quiz places, council decisions, games won. Choose the profile to see its history."),
  [T("Games")]: T("Which games are switched on: for everybody, only for chosen children, or off. Parents can always play. The family council and polls stay open for everybody."),
  [T("Season designs")]: T("The animated scene in the header of the app: seasons, Halloween and Christmas switch themselves every year. Switch them on or off, move the dates or add your own designs (e.g. a birthday week)."),
  [T("Pairs game: photo sets and family crest")]: T("Your own photo sets for the pairs game (e.g. family members) and the family crest that is shown on the card backs and the kiosk."),
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
  [T("Current goals")]: T("The goals running now with their progress. Tap one to change or end it."),
  [T("Home Assistant")]: T("Reminders and push messages through Home Assistant: when children without the daily goal or with open chores are reminded, the notify service for approvals and whether learning coins also count as Family Planer points."),
  [T("About")]: T("The version of Family Quest and what is connected: Home Assistant, the built-in planner and the photo / PDF import."),
  [T("From a file")]: T("Choose or drop a file: YAML, JSON or ZIP packs, CSV or Excel tables (you assign the columns) or – with an API key – a photo or PDF of a word list."),
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
