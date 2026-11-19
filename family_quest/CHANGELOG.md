# Changelog

## 1.1.1

Version 1.1.1 – everything that was tested in the betas 1.1.1-beta.1 … 16.

**Before updating:** download a backup in the parent area (Settings › Backup & restore).

**Changes you will notice:** families whose language isn't German no longer get the German-only learning packs
(German year 5, Thurgau, TG year 5, general knowledge) – packs with learning progress stay, all can be added again
under Learning packs › More packs. The Family Quest panel is now visible to all Home Assistant users (the parent
area still needs the PIN or a linked parent user). Direct access is on by default for new installations.

- **New in the Library:** books (picture books), interactive books (mostly linear with a few choices, several happy
  endings, templates «The princess who didn't want to marry» and «The little fox's birthday») and own vector drawings
  (SVG) for pages, backgrounds, rooms and things – with AI import/export and visibility «only me» (also parents
  can't read it), other children or the whole family.
- **Games:** adventure games (point & click with rooms, things, dialogues and a solvability check) in a new «Custom
  games» group with the family quiz and Pair Hunt (photo sets with presets, ZIP import/export); «24h Endurance» as a
  short, fast team race with battery swaps, pit stops, chicanes, rain and night; Clap the Beat with a run-up bar;
  word games in every language; game prices, rent, free tries, game battery and party mode with Disco theme.
- **Deals:** children trade coins, chores, avatar items, pets and bought games with each other and with parents.
- **Learning:** language courses ask in the learner's own language (progress is kept); German-only packs optional;
  a paste box for AI-made packs; time limits per child for games, learning and internet.
- **Parents:** a dialog with the QR code of the kids' app (print, open); optional sign-in of children with their own
  Home Assistant user; the Home Assistant integration in all languages; all game sections folded with status chips;
  profile dialog in tabs.
- **French and other languages:** a full French pass of the kids' app and the parent area.
- **Reviews:** many fixes from code, security and usability reviews – no deadlock on deal chores, profile ids never
  reused, HA actions only for admins, safer coin bookings, fewer database queries, phone landscape layouts, larger tap
  targets, better contrast in dark mode, focus handling in dialogs, notch-safe game screens.

## 1.1.0

Version 1.1 – everything that was tested in the betas 1.1.0-beta.1 … 15.

**Before updating:** download a backup in the parent area (Settings › Backup & restore). Home Assistant may ask you
to confirm that the app may now write to its config folder – this is only used by the optional Family Quest HA
integration (off by default) and only for `custom_components/familyquest`.

**New defaults – please check parent area › Games:** quick games rent for 100 coins per week and game-corner games
for 20 coins per day (one free try each, other games stay free), and every child has a game battery with 5 charges
(recharging costs 50 coins). Every value can be changed or switched off per game, per family or per child.

- **New games:** Star Runner (3-lane run as your own avatar, the others as ghosts), Escape Room (56 riddles, teams),
  Snack Rush (own snack stand), Traffic Cadet (traffic lights without accidents), the cube solver for 2×2 and 3×3 in
  the game corner; Werewolves from 2 people with bots; Jump with crates, cacti and a cloud parcours.
- **Games page:** running games on top, then the family quiz, «For a game night», «Quick games for in between» and
  the game corner as tiles; a header note (with a chime) when somebody opens a table – join with one tap; ☰ game
  menu in every game (rules, guests, language, sound, leave); who begins: dice, leader or chosen player.
- **Game prices, battery and party mode:** parents set a buy and / or rent price (day, week, month) and free tries
  per game – children unlock games in the shop; children may always join tables a parent opened; game battery with
  recharge, goal and chore bonus and unlimited periods; 🎉 party mode unlocks all games and / or gives unlimited
  battery (optionally lifting time limits) for all or chosen children – with a Disco theme in the app; the one-armed
  bandit gets a win-chance slider.
- **Time per day for each child:** sliders for games, learning and internet, per weekday if wanted (∞ by default).
- **Family:** bulletin boards (sticky notes, texts, drawings, zoom); FamilyTime game wishes and vote; the special
  quiz «Family Quest Facts» made from the family's own data; multilingual quizzes (all 28 templates translated);
  running quizzes can be cancelled.
- **Parent area:** own «Games» menu (active / without bots / inactive, search); «Community» is now «Family»; shop
  with search, own prices, switched-off items and items paid with new XP; learning packs with search, own packs on
  top, own XP and coins per lesson; 15 new avatar backgrounds; the session renews itself after a long pause.
- **Family Quest HA integration** (optional, off by default): devices per child and for the family with sensors
  (XP, level, coins, goal, chores, time left, running games, approvals), an internet switch and actions to book
  points and approve chores and rewards.
- Game names translated, many fixes from code, security and usability reviews, older iPhones display boards
  correctly, backups of older versions can be restored.

## 1.0.0

Version 1 – everything that was tested in the betas 0.4.0-beta.1 … 26 and 1.0.0-beta.1 … 5.

**Before updating:** download a backup in the parent area (Settings › Backup & restore). After the update restart the
app once – the media folder of Home Assistant is now mapped writable (for the photo/PDF import).

- **14 new games** (own menu item, switchable per game and child; alone against bots and / or at a family table,
  guests via QR code, coins for places 1–3, the «No. 1» hat until the next family game):
  Paarjagd (pairs with own photo sets), «Wer bin ich?», Kartenlauf, Stadt-Land-Fluss, Zeichnen & Raten, Fünf Würfel,
  Verbotene Wörter, Heimwärts (race board game), Jass (Schieber), Jump (own lanes, same obstacles for all), Werwölfe
  (party game, the app is the game master), Klatsch den Beat (rhythm), **Schach** (chess – games can be paused and
  continued) and **Dorfmarkt** (property trading in a Swiss village).
- **More to play:** Ping-Pong and Tic-Tac-Toe on two phones, Ping-Pong doubles (2 against 2), the one-armed bandit in
  the game corner, bot reaction time in all bot games.
- **Pets:** pet sitting by a family member or the pet hotel, more pets of one kind, babies, the hamster that mines
  coins, dino egg, goldfish, turtle, aquarium, terrarium and nest.
- **Shop:** many new avatar items (jetpack, wings, laser sword, dark knight helmet, bat mask, devil horns, pirate
  apprentice, pyjamas, round belly …), new slots «on the back», «costume», «figure» and «in the hand»; pranks:
  the **ink bomb** (smears the screen of chosen family members) and the **whoopee cushion** (a fart on all
  speakers of the home); own coin icon.
- **Parents:** list of all running games (end one or all), failed logins folded, parent area link on the login
  screen and in the app menu, refresh button ⟳ everywhere, chore plan in the standard look and fit for phones.
- **Photos from Home Assistant Media** for photo sets and the family crest – only referenced, not copied.
- **Backup:** much smaller (only own data; Home Assistant Media photos as references, the app's own content left
  out), restore in 4 MB pieces (no more «HTTP 413» behind Home Assistant), sizes shown; old photo copies are linked
  back to Home Assistant Media at start.
- **Photo/PDF → draft pack** now uses the AI set up in Home Assistant (AI Task: OpenAI, Google, Anthropic, a local
  Ollama …). The options «Anthropic API key» and «Claude model» are gone.
- Sharp SVG flags and coats of arms, France quiz templates, Domino as a snake, song quiz «the others show the
  solution», many fixes.

## 0.3.0

The big community and family release – everything that was tested in the beta 0.3.0-beta.1 … beta.76.

- **New app menu:** ☰ menu at the top left (Home, Learning, My card box, Shop, Me, Family, Games, Planner, language,
  light / dark, sound, log out), header like the Family Planer with clock and an animated **season design**
  (seasons, Halloween, Christmas and own designs, scheduled in the parent area). Light and dark mode everywhere.
- **Community:** family quiz (own quizzes, templates by region, estimation, map and picture questions), family council,
  polls, **Wichteln** (secret gift giving with rules and planner to-dos), history – collapsed lists with filters.
- **Games** (own menu item, switchable per game and child): bingo, **Errate den Song** (speaker playlist, buzzer,
  countdown, volume, game-show sounds), Tschau Sepp, Kartenkarussell, Texas Hold'em, **Domino** (double-6 / double-9,
  simple or Cuban, teams, Pollona), game corner (Tic-Tac-Toe, Sudoku, Patience, Ping-Pong, Pairs with photo sets and
  family crest) – alone against bots (also own bots of the children) or at a family table, guests via QR code.
- **Learning:** language courses and general knowledge, **My card box** (own flash card decks, words from the lessons
  with one click, Leitner repetition).
- **Family & time:** family calendar (list, day, week, month, year; FamilyTime and OfflineTime; school holidays,
  ICS / CSV, Home Assistant calendars – also in the planner), **internet budget per child** (per day / week, other
  weekdays, block times with «app normal / without games / only a message»), behaviour weather in the overview.
- **Avatar «Me»:** free glasses, braces and hair clips, pink colours, pets clearly visible, new shop items.
- **Parent area:** only through Home Assistant if wanted (login with the Home Assistant user), Home Assistant look,
  works on the phone, ⓘ info for every box, Bring! shopping list sync, season designs, release notes with update check.
- **Security:** own AppArmor profile, PIN throttling, children only see the parts of Home Assistant the planner needs,
  many fixes from a code review.

## 0.2.1

- **Fix: Home Assistant connection.** The app showed «without Home Assistant»: the Supervisor key did not reach the
  app. It now starts with the container environment (and reads the key from the s6 environment as a fallback), so
  push messages, devices, internet time and the Planer's Home Assistant features work again.

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
