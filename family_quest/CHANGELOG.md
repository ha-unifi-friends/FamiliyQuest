# Changelog

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
