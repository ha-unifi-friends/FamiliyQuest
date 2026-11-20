# Changelog

## 1.2.1-beta.3

- Parent area: the box with light/dark mode, language, log out and version always sits at the bottom of the screen

## 1.2.1-beta.2

- Game lobbies: a visible «👥 Invite guests» button in the waiting box of every game (also still in the ☰ menu)
- Guests pick their avatar when joining – 8 quick picks (women, men, grandparents, neutral), random or customize with the free avatar parts – and can change it later in the game via ☰ «My avatar»

## 1.2.1-beta.1

- Invite guests: with a guest WiFi QR code from Home Assistant (e.g. UniFi image entity, chosen in Settings › Home Assistant) the dialog has a switch «🎲 Game | 📶 Guest WiFi» – guests join the WiFi first, then the game; the picture is only shown on signed-in family devices

## 1.1.1-beta.30

- Security: Content-Security-Policy on every page – only Family Quest's own scripts run; pictures and files under /media are served sandboxed, unknown file types only as download
- Parent area code split into thematic files (no change in behaviour)

## 1.1.1-beta.29

- Profile dialog: «Log out everywhere» ends every login of the profile on all devices
- Sign in with Home Assistant: a warning in the parent area when Family Quest does not know the Home Assistant address yet

## 1.1.1-beta.28

- Security: «Sign in with Home Assistant» in the app only talks to the internal Home Assistant or the address set by the parents – a fake Home Assistant can no longer hand out parent access
- Security: parent networks apply to every parent function; parent sessions end after 12 h on the app port (30 days via Home Assistant); a new PIN signs out all devices; per-profile PIN lockout after 5 wrong tries
- Backups with planted database triggers are refused; a damaged backup changes nothing; orphaned entries after a partial restore are removed; privacy snapshots hold the database only (max. 3, max. 30 days)
- Faster and more robust: database writes off the main thread (no hang during Home Assistant backups), new indexes for running games and dates, privacy clean-ups keep the facts statistics, the Family Planer cannot book twice
- Parent area: chores page shows the system in use first, «Points & rules» instead of «Rewards», keyboard-friendly phone menu and period picker, coins in the collapsed child rows, avatar items as cards on phones, translated backup file picker, better contrast, ⓘ never alone on a line

## 1.1.1-beta.27

- Parent area: group headings on the page background with folded tiles on Overview (Children, Parents …), Games, Privacy and Calendar – like Family and Settings
- Dashboard is no longer its own menu item – it is in Settings → App (old links lead there)
- Analytics: tabs next to the title, data source as chips, new Bubble chart (rows × columns, size = value) with the template «Game time by weekday and child»
- AI imports (packs, quizzes, books, adventure games): «Download template for the AI» on top, the prompt asks for a downloadable JSON file, «Copy prompt» below it, import only as a file (no more paste field)

## 1.1.1-beta.26

- Parent area: the menu header has the same tinted background as the personal part – «Family Quest» with ⟳, and below it «⭐ Family Quest App ↗»

## 1.1.1-beta.25

- Parent area: the release notes open from the version at the bottom left and from Settings → About; the personal part of the menu (light/dark, language, log out) has its own background

## 1.1.1-beta.24

- Parent area: Deals is no longer its own menu item – it is a group on the Family page (old links lead there)
- Main menu: Overview, Family, Chores, Learning packs, Rewards, Games, Shop, Calendar, Dashboard, Analytics, History, Privacy, Settings

## 1.1.1-beta.23

- Install guide for iPhone: new first step in Safari – tap the menu icon left of the address, then «Share»

## 1.1.1-beta.22

- Parent area: the Family Quest header of the menu is the link to the kids' app (QR code); the menu starts with Overview
- Refresh icon centred and a bit larger

## 1.1.1-beta.21

- Parent area: new main menu order – Family Quest App, Overview, Family, Learning packs, Games, Chores, Rewards, Shop, Deals, Calendar, Dashboard, Analytics, History, Privacy, Settings
- Refresh button in the parent area no longer shows the old ⟳ character next to the new icon

## 1.1.1-beta.20

- Analytics (new main menu): dashboards with a timeline filter and period picker, reports from templates or an ad-hoc builder (drag dimensions and measures into columns, rows, data, group), 8 chart types, «My reports»
- Privacy (new main menu): retention periods for every kind of data, clean-up runs with preview, automatic backup before each run, past runs, optional nightly clean-up, master switch and a red badge with the number of due entries; balances stay unchanged (balance brought forward)
- Backup: full, data and customizing backups with one restore that detects the kind; environment values (ports, links, HA connection) are kept on restore; hint and button to include Family Quest in the Home Assistant backups; consistent hot backups by Home Assistant
- Season designs show the live weather of a chosen weather sensor and follow day, night and dusk of the real sun
- Parent area tidied up: explanations in ⓘ buttons, small fields side by side, settings in groups (App, Personalisation, Home Assistant, System), Family page with goals, crest, family view and FamilyTime games, History as its own menu item, everything collapsed by default, bigger expand arrow, games grouped like in the app, ⓘ on table headers
- Overview: one collapsible row per child with weather quick-pick and «Edit profile»; failed logins at the bottom
- Wichteln is translated («Secret gift giving»)

## 1.1.1-beta.19

- The ⓘ info button is always right next to its label, also in dialogs

## 1.1.1-beta.18

- Parent area: an ⓘ info button with an explanation on every section and setting
- Settings: every part folded, with a short live status in its header (network access, Home Assistant login, backup, …)
- Kids' app ☰ menu: «📲 Install app» – recognises iPhone/iPad or Android and shows the steps with the real buttons, with an Install button where the browser offers it; also in the parent area «⭐ Family Quest App» dialog
- English addresses: /parents, /guest, /planner – the old German addresses keep working (printed guest QR codes, bookmarks)

## 1.1.1-beta.17

- Sign in with Home Assistant also in the app (tablets): kids and parents linked to a Home Assistant user sign in with their HA account – on by default
- Clear sign-in per profile: no sign-in, PIN, Home Assistant only, or PIN or Home Assistant – enforced on every login; a profile with a HA user and no PIN never logs in without a login
- First start in Home Assistant: name prefilled, no PIN needed – the first parent is linked with the HA user
- Parent area › Chores: the planner in the standard design; no PIN prompts in the planner any more – the signed-in profile decides (children: own to-dos without points)
- 24h Endurance: no stuck start screen any more for a player whose phone slept in the lobby; one clear screen per role
- Pair Hunt: photos made small automatically, reliable multi-photo upload; custom games with a unified layout; quiz question language in the ☰ menu
- Beta and Dev have their own app icons (BETA / DEV band); the parent area link to Home Assistant works when not signed in

## 1.1.1-beta.16

- «Family Quest App» dialog: without direct access it shows only how to switch it on (no QR code that cannot work)
- Direct access (the app in the home network) is now on by default for new installations

## 1.1.1-beta.15

- Language courses in the learner's own language: English, French, Spanish and German (A1–B1 and the year-5 units) ask in the app language of the child – progress is kept when the language changes; a course in your own language isn't offered
- German-only learning packs (German year 5, Thurgau, TG year 5, general knowledge) are no longer installed by default – parents add them under Learning packs › More packs
- Optional: children can sign in with their own Home Assistant user (switch in Settings, link in the child's profile) – never the parent area; the Family Quest panel is visible to all Home Assistant users
- Parent area: «Family Quest App» opens a dialog with the QR code of the kids' app, open in a new tab and print poster

## 1.1.1-beta.14

- Review fixes (code & security): no more deadlock when approving a chore from a deal; profile ids are never reused (a new child can't inherit a deleted child's private books); Home Assistant actions only for HA admins; Facts quiz respects the family view and keeps guests out; deal reservations also in the shop and the Family Planer; clean errors instead of crashes for bad input; coin payouts protected against double booking; far fewer database queries
- Review fixes (UX & touch): games fit on phones in landscape (Clap the Beat, Snack Rush, Domino, Five Dice, Homeward); better contrast in dark mode; larger tap targets and checkboxes; dialogs with focus handling and the app's own confirm dialogs; back button works in the parent area; profile dialog in tabs; status chips on the parent Games page; shop category chips; paste box for the learning-pack AI import; notch-safe game screens; no more «null» texts

## 1.1.1-beta.13

- 24h Endurance runs on batteries: full throttle drains much more, an empty battery means emergency drive mode at walking pace; every team has one spare battery that is swapped at each stop with whatever charge it has – the crew must plug it in early, charging takes about a lap

## 1.1.1-beta.12

- Clap the Beat: four «get ready» clicks before every clap bar – the first note can now be hit

## 1.1.1-beta.11

- «24h Endurance» is back as a short, fast race: short laps with two chicanes (brake before them!), automatic pit stop and driver change after every lap; the pit crew lays out slicks or rain tyres, fills the fuel can and prepares a spare engine after an overheat; day, night and sudden rain; team colour, car number and country; cheering stands, campers with signs and trackside banners
- Interactive books: adventure books now read like a book with Back and Next – most pages simply go on, a few pages offer choices, one or several (happy) endings; editor with «goes on» / «choice» switch and «+ next page»; two new templates «The princess who didn't want to marry» and «The little fox's birthday»
- Books and interactive books optimised for phones in portrait (reader and editor)

## 1.1.1-beta.10

- Own drawings as SVG in books, adventure books and adventure games: a new vector painter (pen, lines, shapes, fill, stamps, gradient backgrounds, move/rotate/scale, layers, undo) for page pictures, backgrounds, rooms, hotspots and items – saved in the book and included in the AI import/export
- Every AI import shows its example prompt in a highlighted box with «Copy prompt» (learning packs, family quiz, books, adventure books, adventure games)

## 1.1.1-beta.9

- Parent area › Games: every game starts collapsed; new «Custom games» group under the running games with Family quiz, Pair Hunt and Adventure games – each with Import and New (New starts with templates)
- Pair Hunt: photo sets with presets, import of several photos or a ZIP, export as ZIP
- Adventure games moved from the Library to the Games (parents and kids) and can be switched on or off per child

## 1.1.1-beta.8

- Parent area › Family › Library: one box each for books, adventure books and adventure games, each with its own Import and New button – no type choice needed any more
- Beta and Dev show the «Experimental» badge in the Home Assistant add-on store

## 1.1.1-beta.7

- New in the Library: 🗝️ adventure games – point & click with rooms, doors, things to look at and take, characters with dialogues, an inventory with «use with» and combining, switches and endings; the server checks that a game can be won
- Editor with hotspots drawn on the room picture, room map, dialogue and rule editors, test play; 39 own pictures of things and characters and 10 extra room backgrounds; three templates in all languages; AI import/export

## 1.1.1-beta.6

- «24h Endurance» and «Beat the Bureaucracy» moved to the new Family Quest Dev add-on (too complex – they will be reworked)
- «My books» is now the «Library» with Book, Adventure book and (soon) Adventure game
- New books are visible to the whole family by default; the adventure-book editor shows page numbers in purple circles, also at every choice

## 1.1.1-beta.5

- Word games in every language: the words of Draw & Guess (259), Who am I? (327 characters) and Forbidden Words (372 cards) are in the translation registry; everybody sees them in their own language and guesses count in the languages at the table
- Bookshelf «My books» with types: new picture books (pages with picture and text, layouts, safe SVG pictures, AI import/export) next to the adventure books
- Sample picture book «Klonk, the Laziest Dwarf in the Mountain» in all languages – parents can hide it

## 1.1.1-beta.4

- New: My adventure books – children and parents write branching stories with scenes, 2–4 choices, good and bad endings and items; emoji, drawings or photos, 24 page backgrounds; card and map editor with a checker; four templates in all languages
- Visibility per book: only me (also parents can't read it), other children or the whole family; optional parent approval; rewards for shared books; endings collected and stars per reader
- Adventure books can be exported and imported in the AI-friendly JSON format (template for your AI)

## 1.1.1-beta.3

- New: Deals – children trade with each other and with parents: coins, chores (once or several times, chore swaps), bought avatar items, pets and games, or any free deal; offer, counter-offer and accept like a chat; promised coins and things are reserved; taken-over chores pay out on parent approval (XP always to the one who did it)
- Parents trade as full partners and can require approval for big deals or pets; overview of all deals, cancel and settle disputes (also via the family council)

## 1.1.1-beta.2

- French pass of the kids' app: card game calls and Swiss suit names, bot names, coin reasons in the history (also older entries), guest pages, game titles, short templates and many server error messages are now translated

## 1.1.1-beta.1

- New team game «24h Endurance»: racing stables with driver, pit crew and race engineer, pit stops (tyres, fuel, repairs), engine overheating, day and night, rain, safety car, a running-start intro and a podium
- New party game «Beat the Bureaucracy»: get your building permit stamped in a town hall full of indifferent clerks – appointments, queues, referrals, trick cards, objections, absurd forms; teams against teams or against the administration
- French pass of the parent area: remaining English and German texts translated, server error messages translatable, release notes shown untouched in English
- Home Assistant integration translated into all 9 languages; coin and internet balances named in the HA language
- Family Quest Facts: percent records always get three wrong answers

## 1.1.0-beta.15

- Game battery: every child has a rechargeable battery with 5 charges; starting a game uses one, recharging costs 50 coins (all values can be changed per family or per child, including unlimited charge for a day, week, month or for good)
- The daily goal and chores (new energy bonus per chore) charge the battery
- Party mode for parents: unlock all games and/or unlimited battery for all or chosen children, optionally lifting game time limits, for a set time – the kids' app switches to a Disco theme

## 1.1.0-beta.14

- Quick games now rent for 100 coins per week and game-corner games for 20 coins per day by default (parents can change every value)
- Free tries: every priced game can be played for free a set number of times before buying or renting (default 1)
- New Family Quest HA integration (off by default): sensors per child and for the family, an internet switch and actions to book points and approve chores and rewards

## 1.1.0-beta.13

- Game prices: parents can set a buy price and a rent price (per day, week or month) per game; children unlock games in the shop
- Locked games show a lock tile with buy and rent buttons
- Children can join family tables a parent opened, even for locked or switched-off games
- One-armed bandit uses the standard price model (default 250 coins) and has a win chance slider from 1 to 10
- New special quiz «Family Quest Facts»: questions made fresh from the family's own data (chores, XP, games, records, shop, pets and more), in all quiz languages; parents can switch it off

## 1.1.0-beta.12

- Time per day for each child (parent area › edit profile): three sliders – games, learning and internet – from minutes to hours up to ∞ (unlimited, the default); «Days» opens a slider per weekday that moves with the main one until you set a day on its own (and docks again when you move it back)
- Limits are kept: game minutes and learning time are counted; when the time is up no new game or lesson starts (a running one can be finished); the app shows the time left
- App › Games: running games on top, the family quest, then tiles «For a game night», «Quick games for in between» and the game corner; a tap opens the game's buttons
- Bulletin board: an eraser that works (tap or wipe), toolbar and zoom fixed at the top, no page zoom with two fingers, instant tool switching
- Cube solver: a finger shows how to turn the cube; every step turns slowly by itself after a moment; Star Runner: the other players are drawn smaller

## 1.1.0-beta.11

- New game «Escape Room»: 56 riddles in 9 kinds (codes, secret writing, observation, patterns, maths, memory, maps, mechanical puzzles, knowledge), new numbers every game, combined door locks; together or two teams; rooms, difficulty, kinds and time limit in the settings; riddles not played yet come first; no bots
- New game «Traffic Cadet» (Verkehrskadett): switch the traffic lights of your own map without accidents or angry drivers; 1–5 worlds from a simple crossing to a roundabout; live view of everybody's accidents and angry drivers; bots, guests, coins

## 1.1.0-beta.10

- New game «Snack Rush» (Imbiss-Express): run your own snack stand – cook step by step on several stations at once, serve before customers get angry; ingredients cost money, angry customers leave without paying, leftovers go to the shelf or the bin; the till decides; live view of everybody's till and angry customers; bots, guests, coins
- FamilyTime games: everybody wishes a game for the next FamilyTime, then the family votes (parents can skip or set a game); children can fix a game for 150 coins; the game shows in the calendar and on the start page; switch and price in parent area › Family / Settings

## 1.1.0-beta.9

- New game «Star Runner» (Sternschnuppen-Lauf): a 3-lane forest run at night – swipe to change lane, up to jump, down to duck; you run as your own avatar, the others as ghosts; bots, guests, coins for places 1–3
- New: bulletin boards (Schwarzes Brett) in Family – endless boards with sticky notes, texts, drawings and shapes, zoom 5–400 %, live with everybody's pointer
- Game corner: cube solver for 2×2 and 3×3 – enter the colours on a 3D cube, then a step-by-step guide
- Jump: landing on crates is safe, new cacti cost a life, a cloud parcours over a cactus field
- Parent area: own «Games» menu (search, status active / without bots / inactive per game); «Community» is now «Family»; game names translated
- Planner: ticking off shopping items works; parents in the app need no planner PIN; the PIN dialog is no longer transparent; shop search
- Quiz titles in the app language everywhere; game table note joins with one tap; running games blink on top of Games
- Many fixes from code, security and usability reviews (e.g. who begins really begins, safer planner rights, quiz size limits, compact pack rows, plurals, currency names, larger tap targets)

## 1.1.0-beta.8

- App: when somebody opens a family game table, everybody else who may play it gets a note in the header (with a chime) – «Mia opened a table: Tschau Sepp» – and joins with one tap

## 1.1.0-beta.7

- Parent area › Learning packs: all own packs (imported, made with the AI or edited) in their own box «Own packs» on top
- Import page: shorter – only «From a file» and «Made with your AI»

## 1.1.0-beta.6

- Parent area: after a long pause every button works again – Home Assistant renews the session by itself (otherwise the PIN login appears with «Session expired») instead of the message «HTTP 401»

## 1.1.0-beta.5

- Werwölfe: playable from 2 people – bots fill the table up to 5 (or up to the number chosen, max. 12) and play every role (Amor, wolves, seer, witch, hunter) and vote; no coins for bots
- App: the refresh button is light purple
- The language list in the game menu (☰) and in the app menu stays on screen; the game menu closes when you go to another page

## 1.1.0-beta.4

- All 28 quiz templates (539 questions) are translated into English, French, Italian, Spanish, Dutch, Polish, Portuguese and Swedish – a quiz made from a template is multilingual, everybody picks the language in the game; the template list shows titles in the app language
- Multilingual quizzes can have up to 9 further languages
- App › Quizzes: a running quiz is shown on top – open it, or cancel it (parents and whoever leads it)

## 1.1.0-beta.3

- Multilingual quizzes: switch it on in the quiz editor, choose a main language and up to 5 further ones – then every question gets fields for them; during the game everybody picks the language of the questions at the top
- The quiz JSON template, import and export know the languages too (an example multilingual quiz is in the template)
- Home: the XP ring also shows all XP so far (Σ)
- Parent area: the photo sets of the pairs games moved from Settings to Community › Paarjagd

## 1.1.0-beta.2

- Parents see every learning pack in the app – also drafts and switched-off packs – to try them out; nothing is locked for them (the daily lesson uses only active packs)
- The «Learning» page in the app: start the daily lesson and every assigned subject on its own, then the language courses
- Learning packs: own XP and coins per finished lesson (overrides the family rule)
- 15 new avatar backgrounds, each unlocked with 500 new XP – the XP account and the level stay as they are
- Parent area › Shop (new): own rewards on top, every avatar item can be switched off, get a new price or be paid with new XP
- Parent area: «Packs» is now «Learning packs», with a search; imported drafts appear on top and can be assigned to children right away; «Try in the app» on every pack

## 1.1.0-beta.1

- ☰ game menu in every running game: rules, invite guests, leader actions, language, light/dark, sound and «Leave the game» (replaces the ✕)
- Who begins: dice (default), game leader or choose a player – set in Parent area › Settings › Games; a banner shows who starts
- A short chime (and a buzz on phones) when it becomes your turn
- Dorfmarkt: open auction with +10 / +25 / +50 buttons, ends 5 seconds after the last bid
- Older iPhones (before iOS 16): Dorfmarkt board and other game boards display correctly
- Backups of older versions can be restored: checked on a test copy first, with a warning, and the current data are kept as before-restore.zip
- Parent area › Packs: imported packs are shown on top in their own category

## 1.0.0-beta.9

- Learning packs and quizzes in a self-describing JSON: the file itself carries English instructions for an AI and a guide to every field (question types, pictures, flags, SVG, cantons, map positions, pack fields, learning forms, maths generators) – template, export and import are the same format
- New: export quizzes (each one or all) – an AI can change, extend or translate them, then import them again
- JSON exports of packs now carry the same explanations; old files still import

## 1.0.0-beta.8

- «Me» page: everything at a glance at the top – level, streak, coins and internet minutes, open tasks (with the chore list), the internet time with one start / pause button, and the own lights and devices; avatar, moods and pets follow below

## 1.0.0-beta.7

- Quiz template for your AI covers every question type, mixed: multiple choice with text or flag answers, questions with a picture (big flag, emoji, an own SVG drawing, canton outline / map / coat of arms), estimation and map questions
- New quiz pictures: a big country flag, a big emoji or an own SVG drawing
- «New quiz» offers «Import» and «Download template» right next to «Make an own quiz»

## 1.0.0-beta.6

- Templates for your AI: English instructions plus the Family Quest format for learning packs (Parent area › Packs › Import) and for quizzes (New quiz) – download or copy, give it to ChatGPT, Claude, Gemini …, upload the answer
- New: import quizzes from a file (multiple choice, estimation and map questions)
- Uploads accept JSON the way AIs write it (code fence, comments, trailing commas)

## 1.0.0-beta.5

- New game «Dorfmarkt»: a property trading board game in a Swiss village (own board with 36 fields, shops, village bus stops, market stalls and market halls, trading, auctions as an option), 2–6 players with bots, by rounds, time or classic, can be paused

## 1.0.0-beta.4

- New game «Schach» (chess): full rules, against bots (easy / normal / hard), on two phones or on one, optional clock – games can be paused and continued later, several at once

## 1.0.0-beta.3

- New game «Klatsch den Beat»: everybody claps a rhythm back at the same time, judged to the millisecond, harder every round, calibration for the phone delay, bots, coins for places 1–3
- Ping-Pong doubles: 2 against 2 on up to four phones, a short front paddle near the net for each team, bots fill empty seats

## 1.0.0-beta.2

- Photo/PDF → draft pack now uses the AI set up in Home Assistant (AI Task: OpenAI, Google, Anthropic, a local Ollama …); the own Anthropic API key option is gone
- The media folder is now mapped writable: the photo is put there only for the moment of the AI call and deleted right after

## 1.0.0-beta.1

- Version 1 – the same state as 0.4.0-beta.26, now in a fresh repository

## 0.4.0-beta.26

- Avatar shop: pirate apprentice costume (3500 coins) – wide white shirt with lacing, dark waistcoat with brass buttons

## 0.4.0-beta.25

- Shop prank «Whoopee cushion» (300 coins, 3 uses): a fart sound as an announcement on all switched-on speakers of Home Assistant at half volume
- Avatar shop: bat mask (500 coins) and devil horns (600 coins)

## 0.4.0-beta.24

- Shop prank «Ink bomb» (500 coins, one throw each): smears the screen of the chosen family members with ink, they wipe it clean with the finger; everybody can be hit once a day
- Avatar shop: laser sword (1500 coins, new slot «in the hand») and dark knight helmet (2500 coins)

## 0.4.0-beta.23

- New game «Jass» (Schieber: Swiss or French cards, trump / Obenabe / Undeufe / push, Weis and Stöck, bots easy to hard, teams)
- New game «Jump» (everybody in an own lane, the same obstacles for all, 3 lives, getting faster, alone for a record or as a family)
- New game «Werwölfe» (party game for 5–12 in one room, the app is the game master: secret roles, night and day, vote on every phone)
- Backup: old copies of Home Assistant Media photos (until beta.19) are found again in Home Assistant Media at start and replaced by references – the backup becomes much smaller

## 0.4.0-beta.22

- New game «Heimwärts» (race board game for 2–4 in the style of Ludo / Eile mit Weile, alone against bots or as a family table, optional benches rule, coins for places 1–3)
- Refresh button ⟳ in the header of the app and of the parent area

## 0.4.0-beta.21

- New game «Verbotene Wörter» (explain a word without the forbidden words, teams or everyone for themselves, timer, 372 German cards, coins for places 1–3)
- Login screen and app menu: link to the parent area (opens Home Assistant when the parent area is only offered there)
- Parent area: failed logins folded with their number in the title; clearer help text for current goals

## 0.4.0-beta.20

- New game «Fünf Würfel» (dice, 13 rounds, alone against bots or as a family table, coins for places 1–3)
- Backup: restore now uploads in 4 MB pieces – no more HTTP 413 behind Home Assistant
- Backup is much smaller: pictures from Home Assistant Media are kept as references, the app's own pack pictures are left out, the database is compacted; the backup section shows what takes how much room
- Restore: the planner no longer books its points a second time after a restore
- Chore plan in the parent area: standard look and fits on phones

## 0.4.0-beta.19

- Planner page: only one ☰ menu button – the planner's own one (meant for the Home Assistant sidebar) is gone

## 0.4.0-beta.18

- «No. 1» hat: who wins a family game (at least two people of the family, not alone against bots) wears a golden hat with a 1 on the avatar – until the next family game they play: second place or worse and the hat is gone; works in every family game (quiz, bingo, guess the song, poker, card games, domino, Paarjagd, Wer bin ich?, Kartenlauf, Stadt-Land-Fluss, Zeichnen & Raten)

## 0.4.0-beta.17

- New family game «Zeichnen & Raten» 🎨: one draws a word on their device (colours, brush sizes, eraser, undo), the others see the drawing live and guess in the chat; hint letters, points by speed, the drawer scores for every right guess; coins for places 1–3
- Pets: more pets of one kind (same price, at most 6 per kind); two healthy pets at least 3 days old can have 1–2 babies (then they rest 14 days); new pets: dinosaur (starts as an egg and hatches on day 1), goldfish, turtle – with aquarium, terrarium and dino nest; baby hamsters mine from 7 days
- Shop: jetpack, wings, chicken suit, camo sweater, helmet, mouse ears hat, drinking helmet with straws, white wireless earbuds, white underpants on the head, T-shirt «I ♥ 🐾», round belly, pyjamas, sleep mask, nightcap, rainbow background, monocle – new avatar places «on the back», «costume» and «figure»
- Coins have their own golden icon instead of the 🪙 emoji (which looks like a moon on some devices)
- Game corner: one-armed bandit «Lucky Star» – buy it once for 150 coins, then 1 coin per spin, 3 spins a day; drawn on the server, about 98.6 % paid back
- Duels for two on two devices: Tic-Tac-Toe and now Ping-Pong too – a «Duel for two» card on the Games page; «Pairs» left the game corner (the Paarjagd does it)
- Parent area: «Running games» under Community – end any running game or all of them
- Guess the song: new option «everybody who did not buzz shows the solution» – the new default

## 0.4.0-beta.16

- New family game «Stadt-Land-Fluss» 🏙️: a letter is drawn, everybody fills in the categories on their own device (16 built-in categories plus own ones, 3–10 rounds, time limit or «Stopp!» with 10 seconds of grace); then everybody reviews the answers – 👎 on answers that don't count (majority of the others decides, the leader can override); 20 points for the only answer, 10 for an own one, 5 for the same as someone else; coins for places 1–3 at family tables; guests via QR code

## 0.4.0-beta.15

- New board game «Kartenlauf» 🏁 (mechanics after the traditional game Tock): 2–4 players, at 4 optionally teams of two; bring your 4 marbles home with cards – A 1/11 or out, K 13 or out, Q 12, J swaps two marbles, 4 forwards or backwards, 7 split among your marbles (passed marbles go back), joker for any card; protected start field, kicking, card exchange with the partner each round; bots in 3 levels with reaction time; house rules for the 7 and the joker; coins for places 1–3 at family tables; guests via QR code
- Fix: a running family quiz no longer traps the parent area – under «Community» it is a card with «Open» and «End»; ✕ goes back to the card

## 0.4.0-beta.14

- Family quiz: five new templates for France – France in general, the 13 regions and their capitals, history, food and culture, and «Where is it? (France)» on the map; new region filter «France»

## 0.4.0-beta.13

- New family game «Wer bin ich?» 🎭: everybody gets a secret character from a category (animals, jobs, food, countries, Swiss places, fairy tales, things at home, sports, famous people) – you see the others' characters but not your own and find it with yes/no questions, in turn; the others answer with yes / no / don't know; guess «I am …» (small typos are fine) or give up; coins for places 1–3 at family tables (set by the parents, like Paarjagd); guests can join via QR code

## 0.4.0-beta.12

- Fix: tapping «Fetch early» twice paid the pet hotel back twice, booking it twice charged twice – pet changes now run one at a time (also no doubled hamster coins, no lost feeding)
- Fix: an early fetch from the pet hotel pays back the price that was paid, not today's price
- Fix: coins for a perfect lesson count towards the daily coin limit of lessons and cannot be booked twice
- Fix: while a family member looks after a pet, the owner's holiday pause no longer stops the bars; the sitter's app updates when the sitting ends or the pet dies; pets of archived profiles are left alone
- Fix: photos of a set could be lost when two saves overlapped during an upload
- Home Assistant Media picker: only the pictures in view are loaded (large camera folders stay fast), at most 40 at once; transparent PNG crests keep their transparency
- Family page: no longer redraws while somebody is typing (e.g. an idea for the family council)
- Settings: invalid numbers (Infinity) are refused

## 0.4.0-beta.11

- Pet sitting: hand a pet to a family member until a day (they feed, play and wash it under «Pets in my care», the food is on them) – or book the Family Quest pet hotel for 1–30 days (coins per day set by the parents, default 10): no decay, the pet comes back fed, happy and clean; fetched early, unused full days are paid back
- New special pet: the hamster (300 coins) – while it is healthy (every bar at least 50) it runs in its wheel and mines coins for its owner (default 15 a day, 5 more than a day in the pet hotel; parents can change it). New house: hamster cage

## 0.4.0-beta.10

- Photo sets (pairs game, Paarjagd): take pictures from Home Assistant Media (Media → My media) – folder browser with thumbnails, «Open Home Assistant Media» in a new tab and «Refresh»; chosen pictures are copied into Family Quest and saved right away (the app needs a restart once after the update to see the media folder)
- Photo upload fixed: iPhone photos (HEIC) are turned into JPEG in the browser, errors are shown per photo, sets are saved automatically
- Family crest: its own section in Settings; it can be an own picture (upload or Home Assistant Media)
- Games with bots: the reaction time of the bots can be set when starting a game (at once … 5 s)

## 0.4.0-beta.9

- Fix: «Family Quest App» in the parent area inside Home Assistant (e.g. the companion app on iPhone) showed «401: Unauthorized» – it now opens the app through the direct access in the home network (http://<host>:<port>/app) with the normal login; without direct access the app opens right inside Home Assistant

## 0.4.0-beta.8

- Domino: the tiles are laid end to end as one connected snake like on a real table – doubles stand crosswise, an upright tile at the row end connects to the next row, which runs back

## 0.4.0-beta.7

- Paarjagd: own pictures – upload and manage photo sets right in the Paarjagd settings; every photo becomes a pair
- Flag quizzes: country flags are now sharp SVG pictures instead of emoji (also on Windows)
- Canton coat of arms quiz: detailed, smooth vector coats of arms in a shield instead of the pixel symbols

## 0.4.0-beta.6

- Parent area: a loading spinner while a page or calendar view loads; if loading fails, a message with «Try again» appears instead of an empty or broken page.

## 0.4.0-beta.5

- Domino: much bigger tiles – their size follows the free space (6 per row on phones); bigger tiles in the hand on large screens.

## 0.4.0-beta.4

- Pets: furnish and dress them – buy outfits, houses and furniture; with a house and furniture the mood drops more slowly, new outfits make the pet happy. Parents choose: pay with coins, XP or both (XP purchases never cost a level).

## 0.4.0-beta.3

- Pets need care: feed (costs coins), play, wash – a pet that gets no care at all for 3 days is lost. Warnings before, push message to the parents.
- Pets grow: baby (up to 6 days), young (up to 29), adult; the badge shows the age in days. Own names.
- Holiday care: parents pause the care per child; holiday days marked «away» in the planner pause it automatically.
- All own pets can play along as bots. New pet: degu.

## 0.4.0-beta.2

- «Open Web UI» and the entry in the Home Assistant sidebar now always open the parent area; the app has its own address …/app.
- No more black screen: no offline cache inside Home Assistant, and if the page does not start, «Reload» appears.

## 0.4.0-beta.1

- New game Paarjagd: find pairs live at the family table (everybody on their own device) or alone against bots – parents set how many coins places 1, 2 and 3 get (only with at least 2 people).
- The start page, Games and Family update themselves when somebody opens a game, a table or a vote.
- Settings › Learning: coins for a perfect lesson (default 5).
- Review fixes: calendar on phones, calendar days in every time zone, block time «only a message» enforced on the server too, new games respect restricted game access.

## 0.3.0-beta.76

- Avatar: pets (dog, cat, owl, parrot) are now clearly visible – as a badge at the bottom right instead of half cut off.

## 0.3.0-beta.75

- Parent area on phones: menu via ☰ (slides in from the left), slim bar with the current area, buttons and tables fit the width, pop-ups use the whole screen.

## 0.3.0-beta.74

- Planner: the «Events» row shows the events of the Family Quest calendar and of the Home Assistant calendars chosen in the parent area; each calendar can be switched on and off in the legend.

## 0.3.0-beta.73

- Parent area: an ⓘ button on every page, every box (right of the title) and at the top right of pop-ups – it explains exactly what it is for.
- Planner: ☰ menu on the left like in the app, «Check holidays» next to the calendar, only «Refresh» on the right.
- App: «Games» is its own menu item; «Family» keeps the family council, polls and Wichteln.

## 0.3.0-beta.72

- Tschau Sepp / Kartenkarussell: tap the card back directly – the chosen one is marked, no dropdown any more.

## 0.3.0-beta.71

- Parent menu: version number and Home Assistant status at the very bottom, below «Release notes».

## 0.3.0-beta.70

- Errate den Song: new own sounds after your examples – game-show chime for right, buzzer for wrong (MP3, also on the speaker).

## 0.3.0-beta.69

- Family quiz in the same look as Wichteln: filter «Not played yet / Played», collapsed titles; opening one shows how often and when it was played and who won.
- Domino: the line of tiles snakes – at most 8 tiles per row on phones, every second row runs back, the green table scrolls.

## 0.3.0-beta.68

- New game Domino: double-6 or double-9 (pip numbers in their own colours), simple or Cuban (10 tiles, teams of two, up to 100 points), the winning team starts, choose the end when laying a tile, «Pass» clearly shown, score sheet per round, Pollona highlighted – alone against bots or at the family table, guests too.

## 0.3.0-beta.67

- Errate den Song: after the verdict «ping» for right and «brrr» for wrong – on every device and as an announcement on the speaker (the playlist goes on afterwards; needs the direct access).

## 0.3.0-beta.66

- New app menu: ☰ at the top left with every area, language, light/dark, sound, season design and log out – no bar at the bottom any more.
- Header like the Family Planer with clock, animated season scene and the buttons of the current area; «Avatar» is now called «Me».
- Season designs: seasons, Halloween and Christmas automatically; in the parent area switch them on/off, move the dates and plan own designs.

## 0.3.0-beta.65

- Community tidied up: family council, polls and Wichteln as a collapsed list with the filter Active / Closed – tap to open.
- Family council like the polls: the vote settings in a pop-up.
- Family quiz: the templates only appear with «+ New quiz».

## 0.3.0-beta.64

- Errate den Song: new setting «Who shows the solution» – who buzzed or only the game leader.

## 0.3.0-beta.63

- Calendar in the parent area: list, day, week, month and year views – the list only appears in the «List» view.

## 0.3.0-beta.62

- Parent area: today's weather in the overview, the weather settings under Settings – no own menu item any more.
- Import via «📥 Import» in Packs instead of its own menu item.

## 0.3.0-beta.61

- Internet budget per child: default budget per day or week with the time it starts again, another budget on certain weekdays.
- Block times per child (also over midnight): internet off, Family Quest normal / without games / only the message «OfflineTime».

## 0.3.0-beta.60

- Release notes: shows whether an update is available, and «Check for updates» opens the apps page of Home Assistant in a new tab.
- Dates and times everywhere in the format of the chosen language.

## 0.3.0-beta.59

- Start and pause the internet time right in «Points and goodies».
- Own AppArmor profile (security rating 8).

## 0.3.0-beta.58

- My card box: own flash card decks for everybody, add words from lessons and packs with one click (📇), repeat with the Leitner boxes, status per card (known, learning, due, new).
- Shop: twirled moustache for 1000 coins.

## 0.3.0-beta.57

- New slogan: Organize your family life with gamification.

## 0.3.0-beta.56

- Wichteln: enter a date – everybody gets a to-do in the planner (without the receiver's name), tick it off in the planner or with «Present ready».
- Parent menu: «Release notes» button below Log out.

## 0.3.0-beta.55

- The version number in the parent menu opens the app page in Home Assistant.

## 0.3.0-beta.54

- Wichteln: occasion, participants, rules (parents / children not among each other), drawn at random – everybody only sees whom they give to. The parent-area hint links directly to Home Assistant.

## 0.3.0-beta.53

- Errate den Song: the game leader controls the volume of the speaker
- Errate den Song: after a buzz a countdown (default 5 s, setting) runs before the solution can be shown

## 0.3.0-beta.52

- Security: children only see the parts of Home Assistant the planner needs (no locations, cameras, locks)
- Security: PIN attempts are limited per device and counted before checking; a new PIN, archiving or deleting a profile ends its logins (everybody logs in once again after this update)
- Fixes: poker alone against bots ends no more when you go all-in; Tschau Sepp with many players; quiz joins, duel invitations, song skip while paused, shop double taps, internet minutes
- Everybody of the family who plays can invite guests (not only who leads the game)

## 0.3.0-beta.51

- Avatar: pink for clothes and hair
- Avatar: glasses (three kinds), braces and hair clips free for everybody – no shop needed
- Parent area: «Family Quest App» opens in a new tab

## 0.3.0-beta.50

- Fix: stopping a quiz no longer shows an error message (same for ending bingo and card games)
- Parent area: app, light/dark, language and log out one below the other at the bottom of the menu, written out

## 0.3.0-beta.49

- Calendar: FamilyTime – highlighted with a countdown in the app and on the dashboard
- Calendar: OfflineTime – internet off and/or app games locked for all or chosen children, or just a notice

## 0.3.0-beta.48

- New game «Errate den Song»: choose a speaker with a playlist – buzzer, the others judge, cover, artist and title from the speaker
- Parent area: «Open in the app» for every game – opens the app in a new tab, logged in as you
- Parent area › Community: family council and polls first, then the games

## 0.3.0-beta.47

- Avatar › My bots: children make their own bots and can share them with siblings – they play Tschau Sepp, Kartenkarussell and Texas Hold'em with you

## 0.3.0-beta.46

- Texas Hold'em alone against bots – easy, normal or hard, on your own table
- Light / dark switch top right (app) and next to the language (parent area)
- Poker in German: «Passen» for check, «Aussteigen» for fold

## 0.3.0-beta.45

- Family council: «New topic» opens a window – first ideas, rule of the vote, collect first or vote right away
- Settings › Games: every game on its own – for everybody, only chosen children or off
- Parents: choose the Home Assistant user; the PIN is only for logging in to the app on another device
- Parent area: buttons to add something always top right; colourful icons and tiles in the Family Quest colours

## 0.3.0-beta.44

- Parent area only through Home Assistant: the app port is then only for the children (no second port needed)
- Parent area in the plain look of Home Assistant – takes over the colours of your HA theme
- Quiz templates: filter by region (general, Switzerland, Germany, Austria, Netherlands) and new templates for Germany, Austria and the Netherlands
- Shopping list: Bring! lists from Home Assistant can be shown as a smart list in the planner

## 0.3.0-beta.43

- Quiz and games fit on one phone screen – no more scrolling: answers as 2×2 tiles, the buttons of the game leader always visible at the bottom
- Bingo, poker, card games and the game corner (now full screen) adapt to the height of the screen

## 0.3.0-beta.42

- New quiz template «Kantonswappen erkennen» – which canton has this coat of arms?
- Family quiz: the question counter no longer slips under the close button

## 0.3.0-beta.41

- Tic-Tac-Toe on two devices: invite somebody of the family – the invitation pops up in their app
- The family crest is shown on the kiosk dashboard and on the printed poster

## 0.3.0-beta.40

- Game corner: Pairs – animals, fruit, vehicles, sea or your own photo sets; alone, against the app or 2–4 players
- Parent area › Settings: photo sets for Pairs and a family crest (also as card back)
- Fix: «null» no longer appears on the parent PIN page

## 0.3.0-beta.39

- New game corner in Family: Tic-Tac-Toe, Sudoku (4×4 to 9×9), Patience and Ping-Pong – against the app or two players on one device

## 0.3.0-beta.38

- Family quiz: estimation questions – slider or number, the closest answer wins
- Family quiz: map questions – everybody sets a pin on the map of Switzerland or Europe, the closest pin wins
- Quiz editor: question type multiple choice, estimate or map; new templates Schätzfragen, Wo liegt das? (Schweiz / Europa)

## 0.3.0-beta.37

- New card games with bots: 🂡 Tschau Sepp (Swiss or French cards) and 🎠 Kartenkarussell (own cards) – alone against animal bots or as a family table (guests too), special cards, calls, rounds, card backs. New quiz templates with pictures: cantons by outline and on the map

## 0.3.0-beta.36

- Polls next to the family council: a question with answers – one or several, anonymous or with names, optionally until a time; results as bars, reminder on the start page

## 0.3.0-beta.35

- Weather alarm: choose a weather entity (Dashboard → Weather alarm) – rain, thunderstorm, snow, wind, cold or heat in the next hours show what to take along, on the dashboard and the children's start page

## 0.3.0-beta.34

- New game: 🃏 Texas Hold'em with play chips (never coins or points) – on every device, guests too; rules: start chips, blinds, ante, rising blinds, time per move, players; mode «same chips for everybody» or «game leader with a bank» (buy-ins on request)

## 0.3.0-beta.33

- Guest networks (Settings → Access from the network): devices in e.g. the guest Wi-Fi can only join games with a QR code invitation – no family login, no app, no parent area

## 0.3.0-beta.32

- New: 📅 Family calendar – own events, school and public holidays of every canton as templates, iCal and CSV import with duplicate check, Home Assistant calendars read-only; the dashboard shows the family events too

## 0.3.0-beta.31

- Planer: «Building block challenge» instead of a brand name; license and third-party notices

## 0.3.0-beta.30

- Own look for the answer tiles in quiz and lessons: ♠ ♥ ♦ ♣ on violet, raspberry, orange and petrol; UniFi blueprint removed (the UniFi rule switch in the child's profile replaces it)

## 0.3.0-beta.29

- Guests in family games: «👥 Invite guests» shows a QR code – guests type a name and play quiz or bingo on their own phone (can be switched off under Settings → Games); fix: dialogs (rules, invitation) above the full-screen game

## 0.3.0-beta.28

- Family council: choose simple, absolute or unanimous majority when the vote starts, optionally «parents and children» (the winner needs a parent's and a child's vote); no decision → vote again or run-off between the two best

## 0.3.0-beta.27

- Chore plan in the parent area now in the Family Quest look (light and dark); all input fields and selects have the same height; «Own texts and languages» folded by default

## 0.3.0-beta.26

- Chore plan and planer settings now in the parent area → Chores (no longer in the app); the planer in the app has language and log-out buttons at the top right; settings: «Take over an existing Family Planer» moved to the bottom, only the import

## 0.3.0-beta.25

- Parent area with your Home Assistant user: link it once after the PIN, then no PIN through the sidebar; optionally parent area only through Home Assistant. Copy-link buttons removed (a click into the field selects the address)

## 0.3.0-beta.24

- Devices per child: a whole room (Home Assistant area) can be given; fix: calendar events on the dashboard

## 0.3.0-beta.23

- New: 🖥️ Dashboard – a family screen for any kiosk browser (wall tablet, TV): choose children and content (clock, crown, weather, learning progress, streak, coins, open chores, family goal, Planer to-dos, calendar events); secret link with QR code

## 0.3.0-beta.22

- Overview and profiles in one page (edit per child, parents below, archived profiles); devices as pills before internet minutes; removing a profile: type the name, then archive (restorable) or delete for good

## 0.3.0-beta.21

- Network access: friendly from–to ranges (plus «this device» / «whole network»); packs: switch between «by pack» and «by child»; device picker shows devices with the child's name on top

## 0.3.0-beta.20

- Own texts and languages (settings, CSV import/export); children change their own PIN; logout icon and «Log in» heading; editing a profile keeps the PIN until «Change PIN»; readable error messages; «Family Quest App» link on the parent login

## 0.3.0-beta.19

- Behaviour weather: new parent menu ⛅ Weather – set each child's weather in the list (bonus/malus), 30-day graph, configurable symbols, points and reset time; children see only their own weather

## 0.3.0-beta.18

- Avatar specials in the shop (pirate, viking, unicorn …); parents give a crown for a day; 9 moods with emoji in the parent overview

## 0.3.0-beta.17

- Parent area › Settings › Games: games for everybody, only for chosen children, or off.

## 0.3.0-beta.16

- Home Assistant devices per profile: parents choose lights, switches, blinds, scenes; the app shows «My devices» to switch and dim them.
- Flag quiz in both directions in one template.
- Settings › About: the planner is built in.

## 0.3.0-beta.15

- Games fill the page over the app menus, without switching the browser to full-screen mode.

## 0.3.0-beta.14

- Fixed: the connection to Home Assistant (the access key did not reach the app).

## 0.3.0-beta.13

- One main menu everywhere: the planner keeps the menu (Home, Shop, Avatar, Family, Planner); its header is gone.

## 0.3.0-beta.12

- Parent area: one button «Family Quest App» instead of «Learning app» and «Planner».

## 0.3.0-beta.11

- Bingo: ball carousel, mark your numbers yourself, «BINGO!» is checked; the one who starts sets the rules (speed, line / two lines / full card), the last rules are the default; everybody can show the rules.

## 0.3.0-beta.10

- Language courses: German, French, English, Spanish in A1/A2/B1 and general knowledge – learners choose them under «Language courses & more».
- Profile dialog: edit the avatar, choose UniFi rule and budget entity from lists, create the budget entity, picture PIN for parents too.
- Family quiz in full screen; reversed flag quiz; cantons mixed with neighbours and waters.
- Settings › About shows why Home Assistant is not connected.

## 0.3.0-beta.9

- Family quiz: live quiz show on everybody's device; children make quizzes too; 12 templates (Swiss waters, capitals, flags, food, animals, space …).
- Family council: collect ideas, secret vote, result for everybody.
- Personal history with quiz places and council decisions.

## 0.3.0-beta.8

- Planner in all 9 languages (German: original texts, other languages translated).
- Picture PIN for children: 4 of 12 symbols, tap or draw a line; at login the symbols change places.
- Parent area: failed logins with IP, MAC and device name (UniFi) and who normally logs in from there.
- Parent area: allowed networks for the app and for the parent area (mini firewall).

## 0.3.0-beta.7

- One chore plan: Planner chores appear under «Today's chores» on the children's start page and can be ticked off there.
- Parent area → Chores: move the own chores into the Planner with one button (one-off chores stay).

## 0.3.0-beta.6

- Avatar: the spiky hair no longer looks like a crown.

## 0.3.0-beta.5

- Direct access: port preset (Family Quest 8099, Family Quest Beta 8098) – just switch on direct_access and restart.

## 0.3.0-beta.4

- QR code for tablets and phones (parent area → Settings): children scan it and pick their profile without a Home Assistant login; print it as a poster.

## 0.3.0-beta.3

- Family Planer: every profile is a Planer person, Planer points and coins are one balance (setting in the parent area).
- Take over an existing Family Planer from Home Assistant (parent area → Settings → Family Planer), with photos; points are added up.
- The Planer uses the Family Quest parent PINs – no separate start PIN any more.
- Fixed: the red button text in the parent area was invisible.

## 0.3.0-beta.2

- Beta and stable app now live in the same repository and are shown side by side in Home Assistant.
- Own icon with a «BETA» band.

## 0.3.0-beta.1

First beta: same features as 0.2.0, as its own app «Family Quest Beta».

- Own slug `family_quest_beta`, own data; entities, events and notifications start with `family_quest_beta_`.
- New features are tested here first before they are released in the main repository.

## 0.2.0

- **Family Planer inside Family Quest:** the Family Planer (MIT, magibuilds) now runs in the app – button «Planner» in
  the learning app and in the parent area. Chore plan, special chores, to-dos, lists, awards, seasons and settings
  work without a separate integration (data in the Family Quest database). Linking with the Family Quest profiles,
  import from an existing Family Planer and translations follow in the next versions.
- **Own photos:** upload photos in the card editor (📷 per card or «Add photos as cards»), e.g. family members for
  «Pairs», quiz and flash cards. Photos are scaled down in the browser before uploading.
- **Backup & restore:** everything (database, Planer data, pack pictures) in one file, in the parent area.
- **Mood:** sad avatar face, «Today I feel …» text, quiet message to the parents.
- **Language exercises** show which language to answer in.

## 0.1.0

First version.

- **Learning:** packs (YAML/ZIP) and level packs, learning path with stars, daily lesson, quiz round with timer,
  flash cards, pairs, gap text, listening, typing with special characters, drag & drop sorting, arithmetic trainer
  (number pad, fractions, division with remainder). Leitner repetition per card and per arithmetic skill.
- **Packs included:** Mathematik 5. Klasse (generators), Französisch «La maison», Deutsch (Artikel, Wortarten),
  Englisch «In the classroom», Geografie Kanton Thurgau (7 stations), level pack «5. Klasse Thurgau».
- **Rewards:** accounts, rules with daily limits, shop with approval, levels, streak, badges, avatar editor with
  unlockable items, family view and family goal.
- **Badges:** all badges visible with how to get them, progress bar and the avatar items they unlock.
- **Internet time in the app:** firewall/traffic rule per child, budget in the account «Internet minutes», start/stop
  for the child with countdown, automatic block at zero, stop button for parents, sensor with the remaining minutes.
- **More parents:** add further parent profiles with own PIN and own push target.
- **Chore plan:** own chores with points, frequency, fixed or rotating assignment, duty/bonus, parent confirmation
  (OK / once more, also as push buttons), week bonus, week plan, reminder, open-chores sensor.
- **Card box:** Leitner boxes per pack (new, box 1–5), «repeat due cards» across all units, flash cards per unit.
- **Import / export:** CSV/Excel with column mapping, YAML, JSON (file and API), ZIP, link, photo/PDF via the Claude API
  (optional); drafts and editor; export per pack as ZIP, JSON or YAML and all packs as one JSON file.
- **Home Assistant:** sensors and events per child, Family Planer persons and chores, internet minutes, Family Planer
  points, scripts, push approvals, learning reminders; UniFi blueprint for internet time.
- **Languages:** English, Deutsch, Schwiizerdütsch, Français, Italiano, Español, Nederlands, Polski, Português (Brasil),
  Svenska – the same translation system as the IP Manager for UniFi.
