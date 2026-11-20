// ---------------------------------------------------------------- ⓘ in the parent area
// Every box (right of its title), every page (right of the heading) and every pop-up (top right) gets an info button
// that describes it. The headings are found by their text (English or translated); a heading whose text is not a
// key (a sub-section, a fold without a heading) names its entry with `data-ik` – tests/test_parent_info.py checks the cover.
// An entry is one text or a list of paragraphs (the explanations that used to stand under a title live here now).
// Fields get their own small ⓘ right of the label with fieldInfo(…) – the page itself only shows what is needed
// while using it (errors, live values, warnings, empty lists).
const PARENT_INFO = {
  [T("Overview")]: T("The start page of the parent area: open approvals, today's weather of each child, the family goal and one card per child with XP, learning time, weak spots and the balance. Add children and parents at the top right."),
  [T("Calendar")]: T("The family calendar: events, FamilyTime and OfflineTime. Switch between list, day, week, month and year; tap a day to add an event. Below: holiday templates, calendar files and calendars from Home Assistant."),
  [T("Packs")]: T("Learning packs: switch them on per child, edit them, export them or check drafts. «Import» adds new packs from a file, a link or a photo."),
  [T("Chores")]: T("The chore plan: chores with points, how often they come and who does them (fixed or rotating). Duties are expected, bonus chores bring extra points. Children tick them off, you confirm."),
  [T("Family")]: [
    T("What the family decides and does together: family council, polls, bulletin boards, secret gift giving and the history. Children can take part and open topics too."),
    T("Family council, polls and secret gift giving – children can open topics and vote too. The games are on their own page «Games».")],
  [T("Games")]: T("Every game of the app: switch each one to active, active without bots (no «alone against bots», no bots at the table, no games against the app) or inactive – for everybody or only for chosen children; parents can always play. Start games here, set the coins and end running tables. The search finds a game by its name."),
  [T("Rewards")]: T("Accounts and the shop: what children can buy with their points (vouchers, internet minutes, avatar items, Home Assistant scripts) and the rules how many points an activity gives."),
  [T("Goals")]: T("Weekly goals for a child (e.g. 3 learning days) and the family goal everybody works on together. Reached goals give a bonus."),
  [T("Dashboard")]: [
    T("The kiosk dashboard for a tablet on the wall: what it shows (chores, calendar, weather, points) and the link to open it."),
    T("A screen for the whole family: a wall tablet or TV shows what is going on – without anybody logging in.")],
  [T("Settings")]: [
    T("General settings: what children see in the family comparison, sound, reminders, levels, season designs, weather, logins, network access, translations, backup and the Family Planer."),
    T("Every part is folded – tap a row to open it. The row shows how it is set now.")],
  [T("Import")]: T("Add learning packs: a YAML, JSON, ZIP, CSV or Excel file, a link, or (with an AI in Home Assistant) a photo or PDF of a word list. Everything becomes a draft you check before children see it."),
  [T("Waiting for your approval")]: T("Children bought something in the shop that needs your OK. Approve it (the points are booked) or decline it (the points go back)."),
  [T("Chores to confirm")]: T("Chores children ticked off that need your confirmation before the points are booked. Send one back if it was not done properly."),
  [T("Weather of the day")]: [
    T("The behaviour weather: give each child its weather for today. Sunny gives a bonus, a thunderstorm a malus – only the child sees its own weather. Everybody is back at the default at the reset time."),
    T("Give each child its weather – the bonus or malus is booked right away. Only the child sees its own weather.")],
  [T("Bonus/malus points")]: [
    T("The bonus/malus points of the day (☀️ to ⛈️): the levels with icon, name and points, which account the points go to, the default level and when every day it resets."),
    T("Symbols with bonus (positive) or malus (negative points). The best weather on top.")],
  [T("Family goal")]: [
    T("A goal the whole family reaches together, e.g. 50 lessons this month. Everybody's progress counts; reaching it can unlock a reward."),
    T("All children collect together – so siblings help each other instead of only competing.")],
  [T("Parents")]: [
    T("The parent profiles: each parent logs in with the Home Assistant user or a PIN, confirms chores and rewards and can learn along."),
    T("Every parent has an own PIN for the parent area, can confirm chores and rewards and can learn along.")],
  [T("Archived profiles")]: [
    T("Profiles that were removed with «archive»: hidden, but their history stays. Restore them here or delete them for good."),
    T("Inactive – they cannot log in. Their history is kept.")],
  [T("Failed logins (30 days)")]: [
    T("Wrong PINs of the last 30 days with time and device – to notice when somebody tries to guess a PIN."),
    T("Wrong PINs with the device they came from. «Usually» = who normally logs in successfully from this address.")],
  [T("Family council")]: [
    T("Everybody can bring up a question, collect ideas and then vote secretly. You choose the majority (simple, absolute, unanimous) and whether the winner needs a parent's and a child's vote."),
    T("Everybody can ask the family something, collect ideas and then vote – secretly, one vote each.")],
  [T("Polls")]: [
    T("A quick question to the family with 2 to 12 answers – one or several answers, anonymous or with names, optionally with a closing time. Everybody sees the result after answering."),
    T("Ask the family something – everybody answers on their own device and sees the result afterwards.")],
  [T("Bulletin boards")]: T("Endless pin boards for the whole family: sticky notes, texts, drawings and shapes, zoom from 5 % to 400 %. Everybody of the family works on every board at the same time and sees the others' pointers; guests cannot open them. Who made a board, or a parent, renames, archives or removes it (⋯)."),
  [T("Library")]: [
    T("The family bookshelf: 📕 picture books (pages with a picture and a text, read page by page) and 📖 interactive books (they read like a book; at a few pages the reader chooses how the story goes on – with one or several endings, items if you like). Everybody reads the published books; a sample picture book of Family Quest is on the shelf in the app language. ⚙️ below: the bookshelf per child, approval before the family sees a book, coins and XP for writing. You can edit, unpublish and remove every book except the private ones («Only me»: only the author reads them, parents neither). The 🗝️ adventure games are under Games › Custom games."),
    T("Children and parents write books and interactive books, the whole family reads them. Parents can edit, unpublish and remove every book except the private ones. The adventure games are under Games.")],
  [T("Custom games")]: [
    T("The games with your own content – each the same: 📥 Import (a file, e.g. an export or the answer of an AI), + New (starts with the templates), the list of what you have, then the settings. 🎯 Family quiz: your quizzes. 🧠 Pair Hunt: the photo sets (also for the pairs game of the game corner), import photos or a ZIP file, ⬇️ exports a set. 🗝️ Adventure games: point & click games of the family – approve, edit, play; switched off, the children can neither play nor make them."),
    T("Games with your own content: quizzes, photo sets and adventure games – import them or make new ones from a template.")],
  [T("Secret gift giving")]: [
    T("Secret gift giving: enter the occasion and an optional date, choose who takes part and the rules. The app draws at random who gives to whom; everybody only sees their own. With a date everybody gets a to-do in the planner."),
    T("Who gives a present to whom is drawn at random – everybody sees only their own.")],
  [T("Family quiz")]: T("Your own quizzes and the templates: start a quiz, everybody plays on their own device, you show the next question. Filter by not played yet / played; «New quiz» makes one or takes a template."),
  [T("Running quiz")]: T("The quiz that is running right now: who joined, the current question and the ranking. You lead – show the next question or end the game."),
  [T("Bingo")]: T("Bingo with the whole family: everybody gets a card, the balls come by themselves, players mark their numbers and shout «Bingo!». Start a game or open it in the app."),
  [T("Guess the song")]: T("A speaker of Home Assistant plays its playlist; whoever knows the song buzzes, the others judge. Volume, countdown, who shows the solution and the sounds are set when starting."),
  [T("Tschau Sepp")]: T("The Swiss card game: get rid of your cards first, say «Tschau» and «Sepp». Open a family table or play alone against bots; rules and card back are chosen at the start."),
  [T("Card Carousel")]: T("A colourful card game like the classic with colours and numbers: special cards, draw cards that add up, your own bots. Family table or alone against bots."),
  [T("Domino")]: T("Domino with double-6 or double-9 tiles, simple or Cuban rules, in teams. Tap a tile to play, choose the end, pass when nothing fits. The score sheet counts every round; Pollona = won with the others at 0."),
  [T("Pair Hunt")]: T("The live pairs game: everybody turns cards on their own device, a pair scores and you go again. Choose the cards (emoji or your photo sets), the number of pairs, bots and the card back. Below, set the coins for places 1, 2 and 3 – they are only paid at a family table with at least two people of the family, never alone against bots, to guests or to bots."),
  [T("Who am I?")]: T("The live guessing game: everybody gets a secret character of the chosen category and sees the characters of the others. On your turn ask a yes/no question, guess or give up – the others answer on their devices. Only people play (guests via QR code), no bots. Below, set the coins for places 1, 2 and 3 – only paid at a table with at least two people of the family, never to guests."),
  [T("Card Race")]: T("The race board game with cards: everybody brings four marbles around the board and home – cards say how far, the 7 is split, the jack swaps, kicked marbles go back to the kennel. 2 to 4 players, in teams of two with 4 (partners opposite), bots fill free seats. Below, set the coins for places 1, 2 and 3 – a winning team gets place 1 for both; only paid at a family table with at least two people of the family, never alone against bots, to guests or to bots."),
  [T("City, Country, River")]: T("The word game live: who opens the table chooses 3 to 8 categories (or own ones), the rounds, the time per round (or until somebody calls «Stopp!») and whether «Stopp!» gives the others 10 more seconds. Everybody writes on their own device, then all answers are shown – the others can reject an answer with 👎, who leads can decide. 20 / 10 / 5 points per answer. Only people play (guests via QR code), no bots. Below, set the coins for places 1, 2 and 3 – only paid at a table with at least two people of the family, never to guests."),
  [T("Draw & Guess")]: T("The drawing game live: who opens the table chooses the words (animals, jobs, food, things at home, sports or mixed), how often everybody draws (1 to 3 times), the time to draw (60 / 80 / 120 seconds) and whether letters are shown as hints. The drawer picks one of 3 words and draws it on their device; the others see the drawing live and type guesses – the faster, the more points, the drawer gets 10 points per player who found it. Only people play (guests via QR code), no bots. Below, set the coins for places 1, 2 and 3 – only paid at a table with at least two people of the family, never to guests."),
  [T("Five Dice")]: T("The dice game with five dice live: 13 rounds, in every round everybody rolls on their own device at the same time – up to 3 rolls, tap dice to hold them – and fills one box of the score sheet (or crosses one out). 1 to 6 players, alone or with bots (easy / normal / hard), guests via QR code. 35 bonus with 63 points in the upper section; optional +50 for every further «Fünfling». Below, set the coins for places 1, 2 and 3 – only paid for a game played to the end at a family table with at least two people of the family, never alone against bots, to guests or to bots."),
  [T("Homeward")]: T("The classic race board game live: roll the die (on the server), bring your 4 pieces from the yard around the board and into your home – a 6 brings a piece out and rolls again, landing on another piece sends it back to its yard. 2 to 4 players, alone against 1 to 3 bots (easy / normal / hard) or at the family table with optional bots, guests via QR code. Rule options: benches (Eile mit Weile – safe fields nobody may pass), the exact number into the home, play on for places 2 and 3. Below, set the coins for places 1, 2 and 3 – only paid for a game played to the end at a family table with at least two people of the family, never alone against bots, to guests or to bots."),
  [T("Star Runner")]: T("The endless runner live on a forest path with three lanes: swipe left / right to change the lane, up to jump (logs, puddles), down to duck (low branches); rocks and stumps block a lane. Catch the star sparks ✨ for the village lantern. Everybody runs the same course at the same time on their own device and sees the others as ghosts; 3 lives, it gets faster. Points: metres + 10 per spark. The server replays every swipe and decides hits and sparks itself. Coins for places 1–3 at a family table with at least two people of the family."),
  [T("Jump")]: T("The jumping race live: everybody has their own lane, the obstacles come from the left – tap the big button to jump. All lanes get the same obstacles, it gets faster and later there are double and long ones. Everybody has 1, 3 or 5 lives; who hits an obstacle loses one, the last one still running wins. 1 to 6 players at the family table (guests via QR code), or alone for a high score (the personal best is kept), optionally with practice bots (easy / normal / hard). Below, set the coins for places 1, 2 and 3 – only paid for a game played to the end at a family table with at least two people of the family, never alone, to guests or to bots."),
  [T("Snack Rush")]: T("The snack stand live: everybody runs their own stand on their own device and serves the same customers. Every food is made in steps (grill → assemble, fryer → salt, filling a drink …), every step takes its time, and grill, fryer and oven burn what is left too long – juggle several stations at once. Ingredients cost money, a served customer pays (with a tip for fast service), an angry one walks away without paying. 3, 5 or 8 minutes – the most money in the till wins; optionally out after 3, 5 or 8 angry customers. Who opens the table chooses the level, the food on the menu and bots. Below, set the coins for places 1, 2 and 3 – only paid at a family table with at least two people of the family."),
  [T("Traffic Cadet")]: T("The traffic game live: everybody switches the traffic lights of their own map (tap a light: green → amber → red). All maps get the same streets and cars – from a simple crossing to a T-junction, turning lanes, two crossings and a roundabout (worlds 1–5). Crossing cars at the same time crash, waiting drivers get angry; too many accidents or angry drivers and you are out. Others' accidents, annoyed and angry drivers show live at the top. Alone, with practice bots (easy / normal / hard) or at the family table, guests via QR code. Coins for places 1–3 only at a family table with at least two people of the family."),
  [T("24h Endurance")]: T("A short, fast team race live: 24 race hours in 5, 8 or 12 minutes on the Circuit des Tannes, day and night, with sudden rain showers and two chicanes. After every lap the car drives into the pits by itself and the next person of the team drives; the others plug in the spare battery (it charges over time – the next driver gets it as it is) and prepare the tyres (slicks or rain tyres) on their phones; full throttle drains the battery fast, empty means the emergency drive mode. The most laps wins; teams choose colour, country and car number; bots race along."),
  [T("Forbidden Words")]: T("The explaining game live: one explains a word on their device without saying the 5 forbidden words, the others guess aloud. Who opens the table chooses the cards (easy for younger children, normal or mixed – about 370 German cards), the time per turn (30 to 120 seconds), how often everybody explains and whether «Skip» costs a point. With 4 or more players two teams play (the other team sees the card and can buzz), with 2 or 3 everybody plays for themselves. Only people play (guests via QR code), no bots. Below, set the coins for places 1, 2 and 3 – only paid at a table with at least two people of the family, never to guests."),
  [T("Jass")]: T("The Swiss card game Schieber live: 4 players in 2 teams (partners opposite), any mix of the family, guests and bots (easy / normal / hard). Who is on turn chooses Trumpf, Obenabe or Undeufe or pushes it to the partner; the server deals and checks every card (follow suit, no under-trumping, the Buur may be held back). Swiss or French cards, Weis and Stöck, multipliers, a game to 500–2500 points or a number of rounds. Below, set the coins for each person of the family in the winning team – only paid for a game played to the end at a family table with at least two people of the family, never alone against bots, to guests or to bots."),
  [T("Clap the Beat")]: T("The rhythm game live: every round the app plays a short beat (its own drum sounds), then everybody claps it back on their phone at the same time – a playhead runs over the dots of the pattern. The server judges every clap (perfect ±60 ms, good ±130 ms, extra claps cost points) and ranks everybody the same way; it gets faster from round to round (80 to 140 BPM) with syncopes and pauses, 5 to 8 rounds. A short calibration per device subtracts the sound delay. 1 to 8 players at the family table (guests via QR code), or alone for a personal best, optionally with practice bots (easy / normal / hard). Below, set the coins for places 1, 2 and 3 – only paid for a game played to the end at a family table with at least two people of the family, never alone, to guests or to bots."),
  [T("Werewolves")]: T("The classic social deduction party game in one room, 2 to 12 players (family and guests via QR code; with fewer than 5, bots fill the table): the app is the game master. Everybody gets a secret role on their phone – werewolves, villagers, seer, witch, hunter, Amor. At night only the active role acts on its phone, by day the village talks (timer) and votes on every phone. Who leads chooses the roles (or lets the app choose by the number of players), can move on when somebody is idle and end the game. Coins go to the family members on the winning side."),
  [T("Chess")]: T("Chess with the full rules (check, castling, en passant, promotion, draws by repetition, the 50-move rule and too little material): against a bot (easy: mostly random, normal: looks two moves ahead, hard: thinks deeper), against somebody of the family on two devices (an invitation, or an open seat for guests via QR code) or two people on one device. Optional clock of 5, 10 or 15 minutes per side. Every game can be paused – the clock stops – and continued later, also after a restart; several games per person. Who started a game or a parent deletes a paused game; «Running games» ends any game without a result. Below, set the coins for a win against the family, the hard bot and the normal bot (only after at least 10 own moves)."),
  [T("Escape Room")]: T("The live riddle game: every room (wizard's tower, pirate cabin, space station …) hides riddles in its objects. Every solved riddle reveals a part of the door code; the door needs all parts together. Who opens the table chooses the rooms (1 to 5), the difficulty, the kinds of riddles, all together or two teams and a time limit. The riddles are made new every game; riddles already played come again only when all were played (round counter). A hint costs 60 seconds, a wrong answer 10 seconds. No bots, guests via QR code. Coins only for the team that escaped (two teams: the one out first), at a family table with at least two people of the family."),
  [T("Village Market")]: T("The property-trading board game in a Swiss village, 2 to 6 players (family, guests via QR code, bots easy / normal / hard): roll two dice (on the server), buy shops and places, build market stands and a market hall with a whole colour group, collect rent, trade fields and Taler, mortgage when short. Default: after 30 rounds the richest wins – or a time limit, or classic until one is left. Who leads may pause the game; it is saved and survives a restart. Coins for places 1 to 3 only for a game played to the end at a family table with at least two people of the family."),
  [T("Beat the Bureaucracy")]: T("The family party game in a wonderfully complicated town hall, 2 to 4 teams (one device per team, guests via QR code, bots easy / normal / hard): every team needs all stamps (5, 7 or 9) for its building project. At every counter first comes the scene – «Do you have an appointment?» (argue your way in) or a huge queue (wait or try a trick) – then an authority card: a stamp, a referral, a missing document, a lunch break or a mini-game. Trick cards, objections between the teams, events; optionally one team (or a bot) plays the administration. At the end: the permit certificate and the funniest moments."),
  [T("Texas Hold'em")]: T("Poker with play chips – everybody on their own device, or alone against bots. No real money; the chips start again every game."),
  [T("History")]: T("Everything that happened, newest first: points and coins booked, rewards from the shop and the family history (games won, quiz places, council decisions …). Choose a child or everybody and what to show."),
  [T("Season, time of day & weather designs")]: [
    T("The animated scene in the header of the app: seasons, Halloween and Christmas switch themselves every year. Switch them on or off, move the dates or add your own designs (e.g. a birthday week)."),
    T("The header of the app shows the animated scene of the design of the day – like the Family Planer. Children can switch it off on their device in the ☰ menu.")],
  [T("Pairs game: photo sets")]: T("Your own photo sets for the pairs game and the Paarjagd (e.g. family members, holidays) – from Home Assistant Media or uploaded from this device. Every photo becomes a pair."),
  [T("Family crest")]: [
    T("Your family crest – drawn from colours, pattern and symbol, or your own picture. It is shown on the card backs, on the dashboard and on posters."),
    T("Your family crest – on the card backs of the games, on the dashboard and on posters.")],
  [T("Log in with Home Assistant")]: [
    T("Parents can log in with their Home Assistant user instead of a PIN. Choose whether the parent area may only be opened inside Home Assistant."),
    T("Link a Home Assistant user with a profile (Profiles › edit, for parents and children). Parents then open the parent area in the Home Assistant sidebar without PIN; children open their app there without PIN – never the parent area. With the option below both also sign in on tablets and phones with «Sign in with Home Assistant». Profiles without a linked user log in with their PIN."),
    T("Home Assistant users that are neither linked nor administrators get the children's app with the normal login.")],
  [T("Access from the network")]: [
    T("Which networks may open the app directly (without Home Assistant): e.g. the home network yes, the guest network only for game guests."),
    T("Only devices with an address in these ranges may use Family Quest. A range can also be a single address (leave «to» empty). No range = every network.")],
  [T("Backup & restore")]: [
    T("Download a full backup (everything), a data backup (usage data only) or a customizing backup (settings, profiles and own content), or restore one of them – the restore recognises the kind by itself. Make a backup before big changes."),
    T("Saves your own data in one file: profiles, learning progress, points, chores, planner, own packs, own pictures and settings. Pictures from Home Assistant Media and the app's own content are not copied – only the reference.")],
  [T("Automatic backups")]: [
    T("Home Assistant then saves the app with all its data on its own schedule. The app pauses its writes for a moment while Home Assistant copies it, so the copy of the database is complete."),
    T("The three downloads here are for your own copies: the full backup holds everything, the data backup only the usage data, the customizing backup the settings, profiles and own content (e.g. for a test installation).")],
  [T("Shopping list (Bring!)")]: [
    T("Connects the Family Quest shopping list with a todo list of Home Assistant, e.g. Bring!: items are synchronised both ways."),
    T("A list of Home Assistant becomes a smart list of the planner (sorted by shop sections). It stays one list: what you add or tick in the planner shows up in the Bring! app, and the other way round.")],
  [T("One chore plan: the Planner")]: [
    T("The Family Planer is built in: chores, to-dos, lists and awards. «Holidays» shows who is away and whether chores pause. Its settings (persons, points, lists, holidays …) are folded at the bottom of this page."),
    T("The built-in planner has the bigger chore plan (days, rhythm, time to do it, special chores, awards). Its chores also appear on the children's start page.")],
  [T("Take over an existing Family Planer")]: [
    T("If the Family Planer integration already runs in Home Assistant, take over its persons, chores and settings once."),
    T("From the Family Planer integration in Home Assistant: chores, lists, rewards, points, settings and photos.")],
  [T("Templates: school and public holidays")]: [
    T("Add the school and public holidays of a canton to the calendar with one click."),
    T("School holidays and public holidays of a canton – from the free OpenHolidays service. You see a preview first; what is already in the calendar is left out.")],
  [T("Import a calendar file")]: [
    T("Add events from an ICS or CSV file. Duplicates are marked; you choose which events to take."),
    T("iCal (.ics) from another calendar, or CSV with the columns title; start; end (e.g. 04.07.2026). You see a preview first – duplicates are recognised.")],
  [T("Calendars from Home Assistant")]: [
    T("Show calendars of Home Assistant (read only) in the family calendar, e.g. the school or work calendar."),
    T("Show calendars you already have in Home Assistant (e.g. Google, school, waste collection) in the family calendar – read only.")],
  [T("This week")]: T("The chores of this week per day and child – what is done and what is still open."),
  [T("All chores")]: T("Every chore with its frequency, who does it, the points and whether it is a duty or a bonus. Tap one to change it."),
  [T("Levels")]: T("How many XP are needed for each level. Children see their level in the header."),
  [T("Family view")]: T("What children see when they compare themselves with the others, and whether the sound is on by default."),
  [T("Link for tablets and phones")]: [
    T("The address and QR code to open the app on a tablet or phone in the home network."),
    T("Children scan the code with a tablet or phone in your home network, pick their profile and learn – without a Home Assistant login.")],
  [T("Link for the kiosk browser")]: T("The address of the dashboard for a wall tablet in kiosk mode."),
  [T("What the dashboard shows")]: T("Choose the tiles of the kiosk dashboard: chores, calendar, weather, points, family goal and more."),
  [T("To check")]: [
    T("Imported packs that are drafts: check the cards and publish them – only then children see them."),
    T("Drafts are only visible to children after you publish them.")],
  [T("New event")]: T("A new calendar entry: title, all day or with times, icon and colour. FamilyTime is highlighted with a countdown; OfflineTime switches off the internet and / or the games for the chosen children."),
  [T("New chore")]: T("A chore with points, frequency (daily, weekdays, weekly, once) and who does it – fixed or rotating. Duty = expected, bonus = extra points."),
  [T("New poll")]: T("Ask a question with 2 to 12 answers. Choose one or several answers, anonymous or with names and an optional closing time."),
  [T("New topic")]: T("Bring up a question for the family council. Everybody can add ideas; then you start the vote."),
  [T("New board")]: T("A title and an emoji – then everybody of the family can pin sticky notes, write and draw on it."),
  [T("Edit board")]: T("Change the title and the emoji, archive the board (it can still be looked at, but not changed) or remove it with everything on it."),
  [T("New secret gift giving")]: T("Enter the occasion and an optional date, choose who takes part and the rules (parents not among each other, children not among each other). On «Draw» the pairs are drawn at random."),
  [T("New quiz")]: T("Make your own quiz or take one of the templates (filter by region). The quiz is then in the list and can be played."),
  [T("Edit quiz")]: T("Questions with 2 to 4 answers (the right one marked), estimation questions with a number, map questions or picture questions, and the time per question."),
  [T("Start bingo")]: T("The rules of the bingo: card size, how fast the balls come and what counts as bingo."),
  [T("Start the vote")]: T("Choose the majority the vote needs and whether the winner needs a parent's and a child's vote. Then everybody votes secretly."),
  [T("Book points")]: T("Book points to or from a child by hand, e.g. for a good deed – with a reason the child sees."),
  [T("Add account")]: T("A new points account (e.g. «Batzen» or «Screen minutes») with icon and name; children collect and spend in it."),
  [T("Weekly goal for a child")]: [
    T("A goal for one week, e.g. learning on 4 days or 300 XP. Reached goals give the bonus you set."),
    T("Shown on the child's dashboard, e.g. «finish French unit 3».")],
  [T("Remove profile")]: T("Archive (hidden, history kept, can be restored) or delete for good with all data. Type the name to confirm."),
  [T("Release notes")]: T("What is new in every version of Family Quest. «Check for updates» opens the add-ons page of Home Assistant."),
  [T("Invite guests")]: T("Guests (friends, grandparents) join a game with the QR code on their own phone – without a profile."),
  [T("Own texts and languages")]: [
    T("Change texts of the app or add your own language (e.g. a family dialect) based on an existing one."),
    T("Overwrite single texts of a language, or create your own language (e.g. your dialect) – it starts from a base language. Learning content is not translated here.")],
  [T("Level packs")]: [
    T("Level packs bundle several learning packs for a school level and semester. Switching one on for a child activates all its packs."),
    T("Switching on a level pack switches on all its packs for the child.")],
  [T("Accounts")]: [
    T("The point accounts of the family (e.g. coins, XP, internet minutes): name, icon and whether children can spend from it in the shop."),
    T("XP shows progress and is never spent. Spendable accounts can be used in the shop.")],
  [T("Rules: which action gives how much on which account")]: T("What gives points: a right answer, a lesson, the daily goal, a chore … – how many points on which account and how many at most per day."),
  [T("Shop")]: T("What children can buy with their points: vouchers you fulfil, internet minutes, avatar items or a Home Assistant script. Rewards with approval wait for your OK."),
  [T("Current goals")]: T("All goals that are running now. 🎯 A learning goal is for one child: a whole pack up to a percentage, or one unit with a number of stars. 🤝 A family goal is collected by everybody together on one account, e.g. 2000 coins for a pizza evening. Below each goal: for whom and the target. ✕ deletes a goal; new ones with the buttons at the top right."),
  [T("Home Assistant reminders")]: T("Reminders and push messages through Home Assistant: when children without the daily goal or with open chores are reminded, the notify service for approvals and whether learning coins also count as Family Planer points."),
  [T("About")]: T("The version of Family Quest and what is connected: Home Assistant, the built-in planner and the photo / PDF import."),
  [T("From a file")]: [
    T("Choose or drop a file: YAML, JSON or ZIP packs, CSV or Excel tables (you assign the columns) or – with an AI in Home Assistant – a photo or PDF of a word list."),
    T("Everything imported becomes a draft first. You check it, then publish it for the children."),
    () => P.meta && P.meta.ai ? T("Photo or PDF of a word list: the AI of Home Assistant reads it and makes a draft. Packs from school material stay private.") : null],
  [T("Made with your AI")]: [
    T("The template is a JSON file that describes itself to an AI: English instructions, a guide to every field and an example. JSON exports carry the same explanations, so an AI can also change, extend or translate existing content. The AI answers with a JSON file – upload it, it becomes a draft you check."),
    T("Learning material that fits your child's school year and textbook: the template – and every JSON export of a pack – is a JSON file that explains itself to an AI (instructions and every field). Give it to your favourite AI (ChatGPT, Claude, Gemini …) and say what you need – e.g. «French vocabulary, 5th grade, unit 3», «the words on this photo» or «add 10 cards». Paste the answer below (or save it as a .json file and upload it above). Then check the draft, publish it and assign it to your children.")],
  [T("From a link")]: T("Load a pack from an address in the internet (YAML, JSON or ZIP). It becomes a draft too."),
  [T("Format")]: T("An example of how a pack is written in YAML: subject, level, language and units with cards and exercises."),
  [T("Learning packs")]: T("All learning packs of the family: switch each one on or off per child, see the progress, edit, export or remove a pack. «Import» adds your own packs; drafts wait under «To check» until you publish them."),
  [T("Own packs")]: T("Packs you imported or made yourself. Switch them on per child, edit the cards, export them as a file or delete them."),
  [T("More packs")]: [
    T("Optional packs of the app that are not in the family yet, e.g. content for one language or region. «Add» puts a pack into the family – then switch it on per child."),
    () => String(I18N.lang || "").startsWith("de") ? T("Recommended for German-speaking families: packs with German content (school topics of Switzerland and general knowledge). Add them with one click, then switch them on per child.")
    : T("Packs whose content exists in one language only. They are not added automatically – add them with one click, then switch them on per child.")],
  [T("Imported as draft – to check")]: [
    T("The packs you just imported are drafts: check every card and publish the pack – only then children see it."),
    T("Drafts are only visible to children after you publish them.")],
  [T("Code Workshop")]: [
    T("Children learn programming with puzzle blocks and draw their own programs. Switch it on per child, set the coins for solved puzzles and look at the progress and the programs of the family."),
    T("Block programming for the children: 15 puzzles with the fox and own programs. The time in the workshop counts as learning time.")],
  [T("Today")]: T("Today's chores: what is still open, what waits for your OK and what is done."),
  [T("Planner settings")]: T("The settings of the built-in planner: persons, points, lists, rewards, holidays and more. Rarely needed – that is why they are folded."),
  [T("FamilyTime games")]: [
    T("Games for the FamilyTime events of the calendar: children wish a game and the family votes, or a child buys a fixed game with coins. Switch the wishes on or off, set the price and when the wishes close."),
    T("Wish a game for the next FamilyTime – if there are several wishes, the family votes.")],
  [T("Books")]: T("📕 The picture books of the family: pages with a picture and a text, read page by page. Write a new one, change one or import one from a file."),
  [T("Interactive books")]: T("📖 Books in which the reader decides: on some pages there is a choice and the story goes on differently. Write one yourself or import one."),
  [T("Sample books")]: [
    T("Books that come with the app – read them, or copy one as the start of your own book."),
    T("Ready-made books of Family Quest for the whole family, in the language of the app. Hide them if you do not want them on the shelf.")],
  "sb.settings": T("Which children have the bookshelf, whether books of children need your OK before the family sees them, the sample book, and the coins and XP for writing a book and for reading one to the end."),
  [T("Party mode")]: [
    T("One switch for a party or a game night: every game open, no battery and no game time limit – for all or chosen children and for as long as you choose. It ends by itself."),
    T("Nothing is bought or used during the party – when it ends, everything is as before. The children's app turns to the 🪩 Disco design."),
    T("Every game open, no battery, no time limit – for a party or a game night.")],
  "games.general": T("Settings for every game at once: switch all games on or off, choose who begins a card or board game and whether guests may join with a QR code."),
  [T("Game battery")]: [
    T("Starting a game costs one segment of the child's game battery; recharging costs coins. Set the capacity, the price, unlimited energy and what reaching the daily goal brings. Each child can get its own values (profile › Time & battery)."),
    T("Every child has a game battery. Starting a game (an own table, alone against bots, a game of the game corner) costs one segment – joining a table of somebody else is free and a started game can be finished. Empty: the child recharges for coins. Parents play without a battery."),
    T("Chores can give an energy bonus too (chore plan › ⚡ Energy bonus). Each child's own values: profile › Game battery."),
    T("Empty fields: as the family (parent area › Games › Game battery).")],
  [T("Running games")]: [
    T("All game tables that are running right now and who plays. End a table here when it was forgotten."),
    T("Every game that is running just now – family tables and games alone against bots. Ending works like the «End» button of whoever leads it.")],
  [T("Adventure games")]: T("Point & click games of the family: rooms, things to find, riddles and characters. Make a new one from a template or import one, edit it, and play it at the family table or alone."),
  "cg.quiz": [
    T("Your own quizzes and the templates. Tap a quiz to change its questions; start it for the whole family with the buttons above."),
    T("Play a quiz together – everybody on their own device. Make your own quiz or take one of the templates.")],
  "cg.paarjagd": [
    T("Your own photo sets for Pair Hunt and the pairs game – from Home Assistant Media or uploaded from this device. Every photo becomes a pair; «+ New» starts an empty set."),
    T("Upload the photos from this device – several at once are fine. They are made small automatically.")],
  "cg.adventuregame": T("The adventure games of the family. «+ New» starts from a template, «📥 Import» takes a file; tap a game to edit or play it."),
  [T("Tic-Tac-Toe")]: T("Three in a row in the game corner – against the app or a second player on the same device. Set whether it is active, for whom, and the coins."),
  [T("Ping-Pong")]: T("Bounce the ball back in the game corner – against the app or face to face on one tablet. Set whether it is active, for whom, and the coins."),
  [T("Sudoku")]: T("Sudoku in the game corner, from 4×4 to 9×9. Set whether it is active, for whom, and the coins."),
  [T("Patience")]: T("The card patience of the game corner: sort all cards by suit onto the four piles. Set whether it is active, for whom, and the coins."),
  [T("One-armed bandit")]: T("The slot machine of the game corner: one pull costs 1 coin, three a day. Set whether it is active, for whom, and the jackpot."),
  [T("Deals")]: [
    T("Deals between the children and with you: coins, chores, pets, avatar items, bought games and favours. Make an offer yourself, answer deals that wait for your OK and set the rules at the bottom."),
    T("Children trade coins, chores, pets, avatar items, bought games and favours – with each other and with you. XP can never be traded. Reserved coins cannot be spent until the deal is done or fails.")],
  [T("Waiting for your OK")]: T("Deals between children that need a parent's OK before they start. Open one to accept or decline it."),
  [T("My deals")]: T("Your own deals with the children – open one to answer, change or end it."),
  [T("All running deals")]: T("Every open or running deal of the family: who trades with whom and how far it is."),
  [T("Finished deals")]: T("Deals that are done, declined or cancelled – the most recent ones."),
  [T("Deal settings")]: T("Whether trading is on, which children may trade, what can be traded, the most coins per deal and which deals need your approval."),
  [T("Own rewards")]: [
    T("Rewards you set yourself – vouchers, internet minutes, a Home Assistant script … – with price, account, approval and a weekly limit."),
    T("Your own rewards come first in the children's shop.")],
  [T("Avatar items")]: [
    T("Everything children can buy for their avatar, sorted by kind. Change the prices or switch items off."),
    T("Switch items off (they leave the shop – who has one keeps it), set your own price, or let them be paid with new XP: XP earned from now on – the XP account and the level stay as they are.")],
  "dash.children": T("Which children the dashboard shows."),
  "dash.content": T("The tiles of the dashboard: chores, calendar, weather, points, the family goal … Tick what it shows."),
  "dash.calendars": T("Which calendars the calendar tile of the dashboard shows."),
  "dash.weather": [
    T("A warning on the dashboard when rain is likely: the weather entity of Home Assistant, how many hours ahead and from which chance of rain."),
    T("From a weather entity of Home Assistant: rain, thunderstorm, snow, wind, cold or heat in the next hours → a hint what to take along.")],
  [T("Learning")]: T("The coins for a perfect lesson and the prices around the pets: food, the pet hotel, the coins of the hamster and how the pet shop is paid."),
  [T("Family Quest HA integration")]: [
    T("Sensors and actions in Home Assistant (XP, coins, chores, time left …). Switch it on, copy the token, restart Home Assistant and add the integration «Family Quest»."),
    T("Shows the most important numbers of every child (XP, coins, chores, time left, internet …) as sensors in Home Assistant – with a switch for the internet time and actions to book points and to approve chores and rewards.")],
  "ha.app": [
    T("Tablets and phones can sign in with a Home Assistant user instead of a PIN. Switch it on, check the address of Home Assistant with «Test», and link Home Assistant users with profiles (Profiles › edit)."),
    T("The login screen of the app shows «Sign in with Home Assistant». It opens the login page of Home Assistant (with two-factor authentication when the user has it) and comes back signed in – as the profile linked with that Home Assistant user. Family Quest keeps no Home Assistant password or token.")],
  "net.app": T("The address ranges that may open the app at all. No range = every network."),
  "net.parent": [
    T("The ranges that may also open the parent area, e.g. only the parents' network. No range = like the whole app."),
    T("e.g. only the parents' network – children's devices can then not open the parent area.")],
  "net.guest": [
    T("Guest networks: devices there can only join games with a QR invitation – no login, no app, no parent area."),
    T("e.g. your guest Wi-Fi: devices there can only join games with an invitation (QR code) – no family login, no app, no parent area.")],
  [T("Edit profile")]: T("Everything of one profile in tabs: name, role, sign-in and avatar – for children also learning, time & battery, internet and devices. «Save» at the bottom."),
  [T("New child")]: T("Add a child: name, colour and how it signs in (nothing, PIN or Home Assistant). Everything else can be set later."),
  [T("New parent")]: T("Add a parent: name and how they sign in (PIN or Home Assistant)."),
  "Weather for the designs": T("The scene in the header of the app shows the weather outside: pick a weather entity of Home Assistant and it rains, snows, storms or shines in the design like it does at home – also on the days without a season design. It is the same setting as the weather of the Family Planer cards. «None»: fair weather in the scene."),
  "Day and night follow the sun": T("On: the scene turns to night, dusk and dawn with the real sun of Home Assistant (sun.sun). Off, or without Home Assistant: night from 8 pm to 6 am by the clock."),
  "prof.login": T("How this profile signs in: without anything, with a PIN (digits or symbols), with Home Assistant, or with a PIN or Home Assistant."),
  "prof.time": [
    T("How long the child may play games, learn and use the internet per day – also per weekday. ∞ = no limit."),
    T("Far right ∞ = not limited. 📅 Days: own times per weekday – a weekday moves with the slider above until you move it yourself."),
    T("Games: family games and the game corner – a game already running may be finished. Internet: the free minutes of the internet budget (needs the UniFi firewall rule below); 0 = only minutes from the shop.")],
  "prof.internet": [
    T("The internet time of the child through a firewall rule of Home Assistant (e.g. UniFi): the child starts and stops it in the app, the minutes come from the account «Internet minutes»."),
    T("Optional. Family Quest manages the internet time itself with the UniFi firewall rule; an input_number can also receive the minutes.")],
  "prof.push": T("Approvals of chores and rewards also as a push message to this parent's phone (Companion app), with the buttons OK / No."),
  "prof.avatar": T("The avatar of the profile: face, hair, clothes and the bought items."),
  "prof.devices": [
    T("Devices of Home Assistant this profile may switch in the app, e.g. the light in its own room."),
    T("Lights, switches, fans, blinds, scenes and scripts this person may control in the app – or a whole room (area).")],
  [T("Imported as draft")]: T("What the import made: each pack is a draft. Check it with «Edit» and publish it – only then children see it."),
  [T("Assign the columns")]: T("Tell which column of your table is the question, the answer and the rest, and name the pack. The preview shows the first cards."),
  [T("Home Assistant Media")]: [
    T("Pictures from the media folder of Home Assistant: open a folder and tap the pictures you want. They stay in Home Assistant and are not copied into the backup."),
    T("Upload new photos in the Home Assistant media browser (new tab), then tap «Refresh».")],
  [T("Cube solver")]: T("In the game corner: paint the colours of your puzzle cube and get the moves to solve it, step by step. Set whether it is active and for whom."),
  [T("Private books")]: T("Only their authors can read these books – parents neither. You see only that they exist."),
  [T("New photo set")]: T("Start with a preset – then add photos from this device or from Home Assistant Media. Every photo becomes a pair."),
  "set.app": T("How the app works for the family: the link for tablets and phones, the designs of the header, levels and learning."),
  "set.personal": T("Make the app your own: own texts and languages (e.g. your dialect) and the bonus/malus points of the day."),
  "set.ha": T("Everything with Home Assistant: signing in with a Home Assistant user, the Family Quest integration, reminders and push messages, and the shopping list (Bring!)."),
  "set.system": T("Backup and restore, which networks may open the app, taking over an existing Family Planer and the version of the app."),
  "fam.together": T("What the family plans and decides together: the games for FamilyTime, the family council, polls, bulletin boards and secret gift giving. Children can take part and open topics too."),
  "fam.ours": T("What belongs to your family: the bookshelf, the family crest and what children see when they compare themselves."),
  "prof.learn": T("How this child learns: the daily goal in XP, how long a lesson is and how many new cards it brings, when learning is open and when the app logs out by itself."),
  [T("For a game night")]: T("The longer table games for an evening together: card and board games, party and quiz games – everybody on their own device, with bots and guests."),
  [T("Quick games for in between")]: T("Short live games for a few minutes: dice, jumping, running, cooking, clapping – alone for a high score, with bots or at the family table."),
  [T("Game corner")]: T("The small games of the game corner: alone or two on one device, no family table.")
};

const _infoNorm = s => String(s || "").replace(/ⓘ/g, "").replace(/^[^\p{L}\p{N}]+/u, "").replace(/\s+/g, " ").trim();
// the text of a heading without what changes (counters, «● running now», buttons) – «🎯 Family quiz 4» → «Family quiz»
function infoTitle(el) {
  const c = el.cloneNode(true);
  c.querySelectorAll(".chip, .info-btn, button, input, select, .head-actions, .set-status").forEach(x => x.remove());
  return c.textContent;
}
function infoKey(text) {
  const t = _infoNorm(text);
  if (!t) return null;
  for (const k of Object.keys(PARENT_INFO)) if (t === k || t === I18N.tr(k)) return k;
  return null;
}

/** The info pop-up: the title (as shown) and one or more paragraphs (a function gives them when it opens). */
function showInfo(title, texts) {
  const m = modal(h("div.info-modal", h("h2", "ⓘ ", C(_infoNorm(title))),
    ...[].concat(texts).flatMap(t => typeof t === "function" ? t() : t).filter(Boolean).map(t => h("p.info-text", T(t))),
    h("div.row", h("button.btn", { onclick: () => m.close() }, T("Close")))));
  return m;
}

function infoButton(key, title) {
  return h("button.info-btn", { type: "button", title: T("Info"), "aria-label": T("Info"), onclick: e => {
    e.preventDefault(); e.stopPropagation();
    showInfo(title, PARENT_INFO[key]);
  } }, "ⓘ");
}

/** ⓘ for one field or a small part, right of its label text: fieldInfo(T("…"), …) – a text, several paragraphs or a
 *  function that gives them when tapped (texts that change with the form). The pop-up is titled like the label it stands
 *  in (or `opts.title`). Inside a <label> the tap only opens the info, it does not focus the field. */
function fieldInfo(...texts) {
  const opts = texts.length && texts[texts.length - 1] && typeof texts[texts.length - 1] === "object" && !Array.isArray(texts[texts.length - 1]) ? texts.pop() : {};
  const b = h("button.info-btn.field-info", { type: "button", title: T("Info"), "aria-label": T("Info"), onclick: e => {
    e.preventDefault(); e.stopPropagation();
    showInfo(opts.title ? I18N.tr(opts.title) : infoTitle(b.parentElement), texts);
  } }, "ⓘ");
  return b;
}

// what gets an ⓘ: page titles, the titles of boxes and folds (also the games and the folded settings), the sub-boxes of
// the library and the custom games, pop-ups – and every element with `data-ik` (the key of PARENT_INFO), e.g. a
// sub-section (h3) or a fold without a heading
const INFO_SEL = ["main h1", "section.card > h2", ".sec-head > h2", "details.card > summary > h2", ".set-head > h2", ".cg-group > h2",
  "section.sb-sec > h2", ".modal h2", "[data-ik]"].join(", ");
function decorateInfo(root = document) {
  root.querySelectorAll(INFO_SEL).forEach(el => {
    if (el.dataset.info || el.closest(".info-modal")) return;
    const title = infoTitle(el);
    const key = el.dataset.ik && PARENT_INFO[el.dataset.ik] ? el.dataset.ik : infoKey(title);
    el.dataset.info = key ? "1" : "0";
    if (!key) return;
    el.append(infoButton(key, title));          // always right next to the label – also in dialogs
  });
}

(() => {
  let pending = false;
  const run = () => { pending = false; try { decorateInfo(); } catch (e) { /* never break the page */ } };
  new MutationObserver(() => { if (!pending) { pending = true; setTimeout(run, 60); } }).observe(document.documentElement, { childList: true, subtree: true });
})();
