# Family Quest

Learning in any subject with points, rewards and avatars – for the whole family, inside Home Assistant.

## First start

1. Open **Family Quest** in the sidebar and choose **Parent area** (or open `…/parents`).
2. Create the parent profile. Opened from the Home Assistant sidebar, the name of your Home Assistant user is filled
   in and the profile is linked with that user – a PIN is optional (add one later in the profile; on tablets you can
   use *Sign in with Home Assistant*, see below). Opened on the app port (no Home Assistant user), a PIN (4–8 digits)
   is required.
3. **Profiles › Add child** – name, colour, PIN, daily goal (XP), exercises per lesson,
   new cards per lesson, learning hours (e.g. `07:00-20:00`), automatic logout. With the Family Planer installed,
   **Take over from Family Planer** creates a profile for every person and links it.
4. **Profiles › Add parent** – more parents (each with an own PIN for the parent area). Every parent can confirm
   chores and rewards and can learn along; enter a notify service per parent so approvals reach every parent's phone.
   The last parent profile cannot be removed.
   **PIN for children:** a *picture PIN* comes first – the child picks 4 of 12 symbols in its own order (tap them or
   draw a line; 🔀 brings other symbols). At login the same 12 symbols appear in a new order every time, so a
   watched pattern does not help. 12 × 11 × 10 × 9 = 11 880 combinations – more than a 4-digit PIN. A 4-digit PIN can
   be chosen instead – or another sign-in (🔐 *Sign-in*: no sign-in, PIN, Home Assistant only, PIN or Home Assistant,
   see *Sign-in per profile* below).
5. **Packs** – every child starts with the built-in packs that work in every language (maths, the English and French
   units of year 5 – no course of the child's own language); switch packs or whole level packs on and off per child.
   Packs whose content exists in German only (German grammar, Thurgau geography, the level pack «5. Klasse Thurgau»,
   general knowledge) are under **Learning packs › ➕ More packs** – one click adds them (or all of them at once).

## Options

| Option | Meaning |
| --- | --- |
| `direct_access` | On by default (new installations). Also serve the app in the home network on port 8099 (Family Quest Beta: 8098, Family Quest Dev: 8097; can be changed under *Network*). Without it only Home Assistant ingress can reach the app. Parent area › Settings shows the link as a QR code. |
| `log_level` | Log detail. |

## Data

Everything lives in `/data/family_quest.db` (SQLite) and `/data/media/` – both part of Home Assistant backups.
Additional packs can be placed in `/share/family_quest/packs` (YAML files, folders with YAML + pictures, or ZIP files);
they are read at start. Packs changed in the parent area are not overwritten by the folder copy.

### Backup & restore (parent area › Settings)

Three downloads, one restore:

- **⬇️ Download full backup** – everything (database, own pack pictures, photo sets, book pictures, planner photos).
- **⬇️ Download data backup** – only the family's usage data: ledger (points, coins, XP), learning progress, games
  played and their history, chores done, deals, reward redemptions, behaviour weather, calendar and planner, logs and
  statistics, best scores. No settings, no profiles (their numbers and names are in the backup to match them).
- **⬇️ Download customizing backup** – all settings and configuration, the profiles (PIN hashes, avatars, login
  modes, linked Home Assistant users) and the family's own content: packs, own quizzes, books and adventure games,
  code workshop games, photo sets and the crest, shop and rewards, point rules, chore and goal definitions, deal
  settings, game settings, designs, own texts and languages, saved analytics reports and dashboards. No usage data –
  e.g. to set up a dev or beta installation like the real one, without the data.

The restore has one file field and recognises the kind (backups from older versions are full backups). It shows what will
be replaced and what stays:

- A **full** backup replaces everything.
- A **data** backup replaces the usage data only. Profiles are matched by their number: entries of a profile that does
  not exist here are skipped and listed; a profile with the same number but another name is pointed out first.
- A **customizing** backup replaces settings, profiles and own content; the usage data stay. Profiles that are here
  but not in the backup are **kept** (with their data) – nothing is left without its profile; they are listed.
- Balances are always summed from the ledger, and everything stored next to it (XP per day, spent XP, «new XP from»,
  the planner's booking mark) belongs to the same kind – nothing is left out of date.
- Values that belong to this installation are **never** taken from a backup, of any kind: the Home Assistant panel
  path, the Home Assistant address for «Sign in with Home Assistant», the token of the HA integration (and when it
  last asked), the key of the kiosk dashboard link and «Last backup». The signing key (`secret.key`), the add-on
  options (`direct_access`, port) and the channel are not in the database at all.
- Before every restore the current state is saved as `before-restore.zip` (a full backup) in the data folder.

Which table and setting belongs to which kind is one table in `familyquest/backup.py` (`TABLES`, `SETTINGS`); a test
fails when a new table, migration or setting is not classified.

**Automatic backups:** include Family Quest in Home Assistant's backup settings (Settings › System › Backups, the
button «⚙️ Open backup settings in Home Assistant» goes there). The app is backed up *hot*: before Home Assistant copies
`/data`, it runs `hotbackup.py pre` in the app – the app pauses its writes (reading goes on), checkpoints its SQLite
database (`PRAGMA wal_checkpoint(TRUNCATE)`), and after the copy `hotbackup.py post` lets the writes go on. The pause
never lasts longer than 2 minutes, even if Home Assistant never says it is done.

## Channels: Family Quest, Beta and Dev

Three apps of this repository can run side by side, each with its own data and entities: **Family Quest** (stable,
`family_quest_…`, port 8099), **Family Quest Beta** (the next version for testing, `family_quest_beta_…`, port 8098,
orange «BETA» icon) and **Family Quest Dev** (development builds, `family_quest_dev_…`, port 8097, purple «DEV» icon).
Only the dev app has games that are still being reworked (now: 🏛️ Beat the Bureaucracy) and features still in
development (now: 💡 Code Workshop) – stable and beta do not show them; history entries of earlier games stay.

## The app: menu and season designs

The app has no bar at the bottom any more. At the top left **☰** opens the menu: Home, Learning, My card box, Shop,
**Me** (avatar, own bots, PIN), Family, Planner – and language, light/dark, sound, the season design and log out. The
header shows the clock and the buttons of the page you are on (e.g. «+ New deck»).

**Season designs:** like the Family Planer, the header shows an animated scene for the design of the day. Built in and
scheduled every year: spring, summer, autumn, winter, **Halloween** (20.10.–1.11.) and **Christmas** (1.12.–26.12.);
events win over the seasons. In the parent area under **Settings › 🎨 Season designs** you switch them on or off,
move their dates and add **own designs** (name, icon, colour, scene, from – to; e.g. a birthday week) – own designs
come first. Children can switch the scene off on their device in the ☰ menu. During a **🎉 party** the children's app
shows the **🪩 Disco** design (see Party mode).

## Points and rewards

- **Accounts:** XP (progress, never spent), Coins (spendable), Internet minutes (off by default) – add your own.
- **Rules:** event → amount → account, optional daily limit. Events: correct answer, card that was wrong before,
  fast answer in the quiz, lesson finished, daily goal reached, quiz without mistakes, new badge, chore done,
  7/30 day streak.
- **Shop:** vouchers (parents fulfil them), internet minutes (to the profile's *budget entity*, with a daily limit),
  Family Planer points, Home Assistant script (`script.xyz`, gets `profile`, `reward` as variables), avatar item.
  With *Parents must approve* the amount is reserved and booked back on decline.
- **Push approvals:** in *Settings* choose a notify service of the Companion app; the message has the buttons *OK* and *No*.

### Pets

The pets of the avatar shop (dog, cat, parrot, degu – the owl comes with the badge *Busy bee*) want to be looked after. Under
**Me › 🐾 My pets** every pet has a name (Bello, Minka, Coco, Krümel, Eulalia – tap it to rename), its age in days and three
bars: 🍖 hunger, 😊 mood, 🫧 cleanliness (0–100). Hunger and mood drop from full to empty in about 2 days,
cleanliness in about 3 days.

- **Feed** costs coins (*Settings › Learning › Pets: food costs*, default 2) and gives +40 hunger; **Play** (+35 mood)
  and **Wash** (+50 cleanliness) are free. Bars go up to 100.
- **Warnings:** a bar below 25 shows a banner on the start page («Bello is hungry»); when all three bars are empty a
  red banner shows how many days are left, and the parents get a message once (Home Assistant notification and the
  notify services of *Push approvals*).
- If all bars stay at 0 for **3 days**, the pet dies: it is taken off the avatar, the unlock is removed, a note goes
  into the coins history and the child sees a gentle message at the next login. The pet can be bought again in the
  shop as a new baby (an owl that died costs 120 coins).
- **Growth:** every pet starts as a baby (🍼, days 0–6), is young from day 7 and adult from day 30 – the badge on the
  avatar grows with it and shows the age in days.
- **Holiday care:** in *Overview* each child's card shows the pets; **⏸ Holiday care** stops the bars and the death
  timer until it is switched off. On days the built-in planner has the child away on holiday (holiday found in the
  calendars and decided as «away»), pet care pauses by itself.
- **Bots:** the living pets of a child play along as bots in the card games, Domino, Paarjagd and Texas Hold'em
  (only for their owner).
- **🛍️ Furnish & dress up:** every pet card on the Me page (above *My bots*) shows the pet at home – its house as a
  backdrop, the furniture around it and the pet in its outfit. The button opens the pet shop with three tabs:
  - **Clothes** (30–80): bow, collar, sweater, raincoat, little dress, sunglasses, party hat, crown. The pet wears one
    outfit; the child switches between the bought ones. The first time an outfit is worn the pet gets **+20 mood**
    (once per outfit). The outfit also shows on the pet badge of the avatar.
  - **House** (120–300): dog house, cat basket with scratching tree, bird cage, degu enclosure, castle – any pet may
    live in any house, «★ fits best» marks the one made for its kind. One house is in use at a time.
  - **Furniture** (20–60): bed, food bowl, toy ball, play wheel, cushion, lamp, plant, rug – up to **6** placed at a time.
  - A house makes the mood drop **25 % slower**, each placed piece of furniture another **5 %** (at most **50 %**). A
    house with at least 3 pieces of furniture shows ✨ *Happy home*. Bought items are put on / moved in / placed right
    away and can be changed at any time.
  - Everything belongs to that one pet and is **lost when the pet dies**.
  - **Paying:** *Settings › Learning › Pet shop: pay with* – coins (default), XP, or both (the child chooses coins or
    XP for each purchase; the price is the same number). XP spent in the pet shop lower the XP balance but **not the
    level** (nor the daily goal or the weekly XP): the level counts the XP earned.

## Behaviour weather

Parent area → **⛅ Weather**: one list with every child (avatar, name, today's weather). Tap a symbol in the list to
set it – its bonus or malus is booked right away. A small graph shows each child's weather of the last 30 days
(the worst weather of each day; grey dashes = nothing set).

Below the list you configure the symbols (default ☀️ +5, ⛅ 0, 🌧️ −5, ⛈️ −10 coins – best weather on top), the
account, the daily reset time (default 12:00) and the weather everybody is back at after the reset (the reset books
nothing). Each child sees only its own weather on its start page, never the weather of the others.

## Family calendar

Parent area → **📅 Calendar**: month view (a list on phones) with your own events – all day or with a time, with a
symbol. Below:
- **Templates:** school holidays and public holidays of every Swiss canton and year, from the free OpenHolidays
  service (openholidaysapi.org – Home Assistant needs internet for it). You see a preview first.
- **Import:** iCal files (.ics) or CSV with the columns title; start; end (dates like 04.07.2026 or 2026-07-04).
- **Duplicate check:** an event with the same title and dates (or the same iCal UID) is marked and not taken over.
- **Imports** can be removed again as a whole (e.g. the school holidays of a canton).
- **Calendars from Home Assistant** (Google, school, waste collection …) can be shown in the family calendar – read only.
The kiosk dashboard shows today's and tomorrow's events of the family calendar too.

**Weather alarm:** in Dashboard → *Weather alarm* choose a weather entity of any Home Assistant weather integration.
Rain (from a chosen chance), thunderstorm, snow, strong wind, cold or heat in the next hours → the dashboard (and,
if wanted, the children's start page) shows what to take along – «take your rain jacket or umbrella» …

### The family calendars in the planner

The row **«Events»** of the planner's week shows the events of the Family Quest calendar and of the Home Assistant
calendars chosen in the parent area (Calendar › Calendars from Home Assistant), next to the persons' own calendars.
Tap a calendar in the legend at the top left to switch it off or on – on this device.

### FamilyTime and OfflineTime

Calendar › **+ 👨‍👩‍👧 FamilyTime** / **+ 📵 OfflineTime** (or the kind in the event window):
- **FamilyTime** is highlighted in the calendar, on the start page of the children and on the kiosk dashboard, with a
  countdown («starts in 2 h», «still 45 min – until 20:00»).
- **OfflineTime** can switch off, for all or chosen children: the **internet** (a running internet time stops, it
  cannot be started) and the **games of the app** (learning stays open). Without a tick it is only a notice.

### FamilyTime games: wishes, vote, fix a game for coins

Which game do we play at the next FamilyTime? In the app on the **Family** page (and in the parent area › Family) the
section **🎲 FamilyTime games** lists the FamilyTime events of the next 60 days:
- **Wishes**: every family member (children and parents – never guests) wishes **one** game per FamilyTime: one of the
  app's family games (the ones this person may play, parent area › Games) or a **board game** typed in (free text, max.
  60 letters, e.g. «Monopoly»). The wish can be changed or taken back until the wishes close. The start page shows
  «Wish a game for FamilyTime on Saturday!» until you wished.
- **The wishes close** when a parent taps **Start the vote**, or by themselves *N* hours before the start (setting,
  default 24 h). Only one game wished (also when several people wished the same): it is **set directly**.
- **The vote**: one vote per family member, it can be changed. It ends when everybody voted, when a parent taps **End
  the vote**, or when the FamilyTime starts. The start page shows **Vote now!** until you voted. A **tie**: the parents
  choose one of the leaders or tap **🎲 Random**; a tie still open when the FamilyTime starts is drawn at random.
- **Parents** can also **set a game** directly (one of the wishes or any game), **skip the vote** (no game from the
  wishes this time – they can still set one, a child can still buy one), **clear the wishes** (start over) and
  **remove the game**.
- **Fix a game for 150 coins**: a child pays the price (setting, default 150, 0 = off) and sets the game of a
  FamilyTime that has **no game yet** firmly – the wishes and the vote of that FamilyTime end. Refused when a game is
  set already. If a parent removes a bought game (or deletes the FamilyTime, or makes it an ordinary event), the child
  gets the coins back (ledger events `familytime_game` / `familytime_refund`).
- The game shows on the FamilyTime: «🎲 Game: Tschau Sepp – chosen by vote / bought by Mia / set by Papa» in the
  calendar of the parent area, in the planner's calendar row, on the FamilyTime banner of the start page (from 24 h
  before) and in the section. Everybody of the family gets a history entry when the game is set.
- **Settings** (parent area › Family › FamilyTime games › ⚙️, and the same under Settings › FamilyTime games):
  switch the whole feature on/off (off: children see nothing of it), the coin price, the hours before the start when
  the wishes close.

## Kiosk dashboard

Parent area → **🖥️ Dashboard**: a read-only page for a wall tablet, TV or old phone – any browser, no login.
Choose the children and what it shows: clock, crown, each child's weather, learning progress, streak, coins, open
chores, the family goal, open Planer to-dos and today's events of Home Assistant calendars. Moods and messages to
the parents are never shown. The link contains a secret key (🔄 «New link» makes a new one and the old screens stop);
`&lang=fr-FR` fixes the language. The page refreshes itself and keeps the screen awake where the browser allows it.

## Chore plan (Ämtliplan)

Parent area › **Chores**: add chores with icon, points and account, how often (every day, on certain weekdays, once a
week, once on a date), who (several children) and the assignment – *fixed* (every chosen child does it) or *rotating*
(one child after the other, changing every day or every week). *Duty* chores usually give few or no points, *bonus*
chores the full points. With *Parents confirm* a ticked-off chore waits for *OK* (points are booked) or *Once more*
(back to open). The week plan shows who does what on each day; the rule *All chores of the week done* gives a bonus
(20 coins by default). In *Settings* a chore reminder time announces open chores (via the Family Planer announcement
queue) and fires `family_quest_aemtli_erinnerung`. Chores from the Family Planer appear on the dashboard next to them.
A chore can also carry an **⚡ Energy bonus** – segments of the child's game battery (see Game battery).

## 🤝 Deals (trading between children and with parents)

App menu › **🤝 Deals** (de-CH *Händel*, fr *Échanges*): children trade with each other and with their parents. Each
side of a deal («I give» / «I get») combines any of these building blocks:

- **🪙 Coins** – only coins. **XP can never be traded.**
- **🧹 Chores** of the own chore plan: «I do your chore X» – once, or the next N times of a recurring chore (dates are
  shown). The chore moves to the doer's list («🤝 taken over from Mia») and is no longer the owner's that day. Chores
  of the built-in planner cannot be traded as a chore – use a free deal for them.
- **➕ New task** (deals between a parent and a child): «mow the lawn today» – a one-off chore for the child.
- **🎁 Things**: pets (not in the pet hotel, at a sitter, while pet care is paused, earned with a badge or XP),
  avatar items bought with coins, games **bought** for good. Rented games cannot be traded (they run out).
- **✍️ Free deals** without automation («I help you with your homework»): both confirm «Done ✓» at the end.

**Flow:** A sends an offer, B accepts, rejects or makes a counter-offer with the same building blocks – back and forth
as a chat thread with every version. The deal **stands when both accepted the same version**. Notes below the header
(«New offer from Leo», «Deal stands!» …) and a badge on ☰ show what waits for an answer.

**Execution:** coins and things of a side are the payment for the services (chores, free text) of the other side.
Without services on the other side they change hands as soon as the deal stands. Otherwise they are **reserved**:
reserved coins cannot be spent anywhere (shop, avatar items, game prices, battery recharge, pets, pranks, FamilyTime –
the app uses one «available balance»), reserved things cannot go into another deal or to the pet hotel / a sitter.
When a taken-over chore is approved by a parent (or ticked off, for chores without confirmation), its share is paid
**pro rata** (3 chores for 10 coins: 3 + 3 + 4), the things come with the last one. The chore's own coins go to whoever
does it – or to the original owner when the deal says so; its **XP always go to who did it**. Chores taken over do not
count for the «all chores of the week» bonus. **The deal fails** when a taken-over chore is not done by the end of its
day (week for weekly chores), a parent rejects it («Once more») or it is removed: reservations are released, the open
taken-over chores go back to their owner (the missed one stays with who missed it), both see why. Free deals: if one
says «not done», a parent decides – or either of the two sends it to the **family council** (a vote «done / not done»).
Every transfer has a unique reference and is booked once only.

**Parents** (parent area › **🤝 Deals**): their own deals (they trade too – also from the app), deals waiting for
their OK, all running and finished deals (open, cancel any deal – reservations are released, chores go back), decide
disputed free deals, and the **settings**: trading on/off and per child, which building blocks, max coins per deal,
*big deals need a parent's approval* from a coin threshold (default off, 100 coins), *deals with pets always need
approval*. A deal with a parent never needs approval. Coins a parent gives are **paid by the parents** (booked to the
child like a manual booking – no parent account is charged); coins a child gives to a parent leave the child's account.
Guests cannot trade; nobody can trade with themselves, give what they do not own or put one chore / thing in two
deals at once.

## Shopping list (Bring!)

Parent area › Settings › **Shopping list (Bring!)**: the to-do lists of Home Assistant are listed – Bring! lists
first (from the Bring! integration of Home Assistant). *Show in the planner* makes one of them a smart list of the
built-in planner, sorted by shop sections. It stays one list: what you add or tick in the planner shows up in the
Bring! app and the other way round (Home Assistant syncs it with Bring!).

## Home Assistant

Per child profile (name in lower case, e.g. `mia`):

| Entity | |
| --- | --- |
| `sensor.family_quest_mia_xp_heute` | XP today, attribute `daily_goal` |
| `sensor.family_quest_mia_<account>` | balance of each spendable account, e.g. `_coins` |
| `sensor.family_quest_mia_streak` | days in a row with the daily goal |
| `sensor.family_quest_mia_level` | level, attributes `xp`, `next_level_at` |
| `binary_sensor.family_quest_mia_tagesziel` | on once the daily goal is reached |
| `sensor.family_quest_mia_aemtli_offen` | number of open chores today, attribute `chores` (names) |

When a child sets its avatar to the sad face, the parents get a quiet note (Home Assistant notification and a push
without buttons, once per day) and the parent overview shows «feels sad (since …)». Event: `family_quest_stimmung`.

Events: `family_quest_lektion_fertig`, `family_quest_aemtli_erledigt`, `family_quest_abzeichen`, `family_quest_erinnerung`,
`family_quest_aemtli_erinnerung`
(each with `profile` and `profile_id`). The sensors are written through the REST API, so they are recreated when the app
starts and do not have a unique id.

### Family Quest HA integration (own devices and entities)

For real entities (unique id, one device per child, editable in Home Assistant, with history and areas) Family Quest
brings its own Home Assistant integration (custom component `familyquest`). It is **off by default** – nothing is
copied into the Home Assistant configuration until a parent switches it on.

1. Parent area › Settings › **🏠 Family Quest HA integration** › switch it on. Family Quest
   - makes an **integration token** and shows it **once** (📋 Copy) – only a hash is stored; *🔄 New token* makes a
     new one (the old one stops working, Home Assistant then asks for the new one),
   - copies the integration to `/config/custom_components/familyquest` (and again at every start of the app while it
     is on, so an update of the app updates the integration; *⬇️ Install again* does it by hand). For this the app
     maps the Home Assistant configuration writable (`homeassistant_config:rw`); its AppArmor profile allows writing
     only in `custom_components/familyquest` – everything else (e.g. the Family Planer import) stays read-only.
2. **Restart Home Assistant** (Settings › System › Restart).
3. Settings › Devices & services › **Add integration** › *Family Quest*: keep the suggested address
   (`http://<add-on hostname>:8099`, the app on the internal Supervisor network) and paste the token.

Switched off, the API refuses the token (Home Assistant shows the integration as failed / asks to re-authenticate);
the button *🗑️ Remove from Home Assistant* deletes the folder again (delete the integration under Devices & services
first, then restart Home Assistant). The integration asks the app every **30 seconds** and right after every action.
The API (`/api/integration/state`, `/api/integration/action`, header `Authorization: Bearer <token>`) answers inside
Home Assistant OS only to Home Assistant Core on the Supervisor network – not through ingress, not from the home
network; wrong tokens are limited like wrong PINs.

**Devices and entities** (names follow the language of Home Assistant – English and German included):

| Device | Entity | |
| --- | --- | --- |
| each child | sensor *XP today* | attribute `daily_goal` |
| | sensor *Total XP*, *Level*, *Streak* (days) | level: attribute `next_level_at` |
| | sensor *Daily goal progress* (%) | |
| | sensor per spendable account, e.g. *Coins*, *Internet minutes* | balance |
| | sensor *Open chores* | attributes `chores`, `waiting_for_approval` |
| | sensor *Lessons today* | attribute `learning_minutes_today` |
| | sensor *Internet minutes left* | only with internet time managed by Family Quest; ∞ = state *unknown* + `unlimited: true` |
| | sensor *Game time left today*, *Learning time left today* (min) | ∞ = state *unknown* + `unlimited: true` (games: also during a party that lifts the limits, like the app); `used_today` |
| | binary sensor *Daily goal met*, *Game time used up*, *OfflineTime* | OfflineTime: calendar OfflineTime or a block time of the internet plan |
| | binary sensor *Internet blocked* | internet time not running (attributes `block_until`, `can_start`) |
| | **switch** *Internet* | on = the internet time runs. Off pauses it; on starts it with the child's minutes – same rules as in the app (no minutes, block time or OfflineTime: refused) |
| Family Quest (family) | sensor *Family total XP*, *Family XP today*, *Running games*, *Open votes and polls* | votes: family council votes + open polls |
| | sensor *Waiting for approval* | chores + rewards; attributes `chores` (`task_id`), `rewards` (`redemption_id`) |

**Actions** (Developer tools › Actions; with `return_response` they answer with the result):

- `familyquest.add_points` – `child` (name or id), `account` (default `coins`), `amount` (−10000 … 10000, not 0),
  `reason`: like *Book points* in the parent area (shown in the child's history).
- `familyquest.approve_chore` – `task_id`, `approve` (`false` = «again»).
- `familyquest.approve_reward` – `redemption_id`, `approve` (`false` = reject).

They are **admin actions**: only Home Assistant administrators (and automations / scripts) may call them – a
non-admin Home Assistant user gets «unauthorized». The *Internet* switches are normal entities: every Home Assistant
user who sees them can switch them (always with the rules of the app) – keep them off the dashboards of other users.

Nothing else can be changed from Home Assistant (no profiles, settings, PINs or deletions). The sensors above
(`sensor.family_quest_…` without unique id) are still written as before, so existing automations keep working;
with the integration you can hide or ignore them.

### Family Planer

Family Quest reads the persons and their chore lists (`todo.*`) from the Family Planer's entity registry. Link a profile
with a person (profile dialog) and the child sees today's chores on its dashboard and can tick them off; a chore ticked off
in Family Quest, the Family Planer or the Home Assistant to-do list books the rule *Chore done* once per day. Chores that
were already done when the app started are remembered without points.

### Internet time

**Managed by Family Quest (recommended):** in the child's profile choose the UniFi firewall/traffic rule (the switch the
UniFi Network integration creates for it) and whether the rule blocks the internet while the switch is on. The budget is
the account *Internet minutes* (filled by the shop, rules such as the 7 day streak, or parents with *Book points*). The
child starts and stops the internet time on its dashboard; one minute is booked per started minute and the rule blocks
again at zero. Parents see the remaining minutes in the overview and can stop it. At start of the app every idle rule is
set to «blocked»; running sessions continue. Sensor: `sensor.family_quest_<name>_internetminuten` (attribute `running`).

**Budget entity (optional):** minutes bought in the shop can also be written to an `input_number` in Home Assistant,
e.g. for your own automations.

### Time per day: games, learning, internet

In the profile of a child (parent area › ✏️ › **⏱️ Time per day**) three sliders stand on top of each other:
🎮 **Games per day**, 📚 **Learning per day** and 🌐 **Internet**. A slider starts in minutes (0, 5, 10 … 45 min)
and goes on in hours (1 h … 12 h); far right is **∞ = not limited** – the default for games and learning.

- **📅 Days** next to a slider opens the 7 weekdays (Mon – Sun) below it, each with its own slider. A weekday is
  *docked* (🔗, pale): it moves with the slider above. Move a weekday slider yourself and it is *undocked* (🔓, in
  colour) with its own time; move it back to the value of the slider above and it docks again (or tap 🔓). The number
  on the Days button counts the undocked days; the days open by themselves when one has its own time.
- **Games:** every minute in which a child uses a family game (any game request, also waiting in a running game) or
  the game corner (a heartbeat every minute) counts once – several games at the same time do not count twice. When the
  time is used up the child can start or join no new game, the game corner closes and the Games page says «Game time
  for today is used up – see you tomorrow!». A game already running may be played to the end.
- **Learning:** the learning time of today (finished lessons) counts. When it is used up no new lesson starts; a
  lesson already running can be finished.
- The kid app shows the minutes left today («🎮 25 min left today») on the Games page, the start page / the subject
  page (learning) and in the tiles of «Me». Parents are never limited. A new day starts at midnight.
- **Internet:** the slider is the free budget of the internet time (needs the UniFi rule above); with **per week**
  it is the weekly budget (other steps, no weekdays). **0** = no free budget, only minutes from the shop or rewards
  (the behaviour without a plan); **∞** = the internet may run the whole period (block times and OfflineTime still
  apply).

### Internet budget and block times

Below the internet settings of the child (parent area › ✏️ › Internet minutes) **Internet budget and block times**:

- **Reset:** when the budget starts again (time; for a week also the weekday). The budget itself is the 🌐 slider
  under *Time per day*.
- **Block times:** days and a time from – to (also over midnight, e.g. Mon–Fri 20:00–07:00). The internet stays off
  and you choose what Family Quest still allows: *works normally*, *without games*, or *only a message: OfflineTime*
  (the app shows a full-screen message with a countdown until the block time ends).
- Minutes from the shop or rewards come on top: the budget of the period is used first and is not carried over.

The child sees in the app how much of the budget is left and when it starts again; start / pause is in the card
«Points and goodies».

## Languages

The flag button switches the language (English, Deutsch, Schwiizerdütsch, Français, Italiano, Español, Nederlands,
Polski, Português, Svenska; *Auto* follows the browser). Learning content is never translated.

### Own texts and languages

Settings → **🌐 Own texts and languages**: overwrite single texts of any language (English included) or create your
own language – e.g. your dialect – that starts from a base language and appears in the language picker with its own
symbol. Export a language as CSV (`key;standard;translation`, opens in Excel), translate it and import it again; an
empty translation goes back to the standard. Learning content is not translated here.

## Addresses

- **Home Assistant** («Open Web UI», the sidebar entry): opens the **parent area**.
- **The app** for children: `…/app` – inside Home Assistant as well as on the direct port (`http://<IP>:<port>/app`;
  on the direct port `/` still opens the app too). «Family Quest App» in the parent menu, «Open in the app» and the
  planner link there.
- **Parent area**: `…/parents`, **guest page** (invitations by QR code): `…/guest?c=<code>`, **planner**: `…/planner`.
  The former German addresses `/eltern`, `/gast` and `/planer` still work: they redirect to the new ones (query and
  `#…` are kept), so printed guest QR codes, bookmarks and home screen icons keep working.
- **Install the app** on a phone or tablet: ☰ → «📲 Install app» in the app (or «⭐ Family Quest App» → «📲 Install
  app» in the parent area) shows the steps for iPhone/iPad (Safari: share button → «Add to Home Screen» → «Add») and
  Android (Chrome: ⋮ → «Install app» / «Add to home screen»; Samsung Internet: ≡ → «Add page to» → «Home screen»).
  Where the browser offers it, an «Install» button does it in one tap. The entry is hidden in the installed app.

## Security in the parent area

The add-on runs with its own **AppArmor profile** (`apparmor.txt`): it reads its program files but writes only to
`/data`, `/share` and temporary folders, and may not mount or debug other processes. Together with Ingress this
gives the security rating 8 in Home Assistant.

**Log in with Home Assistant:** link a Home Assistant user with a profile (Profiles › edit › *Home Assistant user*,
for parents and children – one user per profile). When Family Quest is opened from the Home Assistant sidebar, the
app knows the Home Assistant user (the Supervisor tells it – only trusted for requests that really come through Home
Assistant): a linked parent comes into the parent area without PIN, a linked child into its app without PIN – never
into the parent area. There is no extra switch for children: the link is the permission; a child without a link logs
in with its PIN. After the first PIN login in the sidebar the app also offers a parent to link the own user.
Settings → *Log in with Home Assistant* can also close the parent area for PIN logins completely (then it opens only
through Home Assistant; the PIN still works in the app for learning along).

**Sign in with Home Assistant in the app (tablets, phones):** Settings → *Log in with Home Assistant* → *Allow
sign-in with Home Assistant in the app* (off by default). The login screen of the app on the app port then shows
**🏠 Sign in with Home Assistant** – only when at least one profile is linked with a Home Assistant user. How it
works:

1. The app sends the browser to the login page of Home Assistant (`<HA>/auth/authorize`, Home Assistant's normal
   OAuth2 / IndieAuth login – the same as the companion app uses). The *client_id* is the address of the app
   (e.g. `http://192.168.1.10:8099/`), the return address `…/ha-auth/callback` is on the same host, as Home Assistant
   requires. Home Assistant asks for user name and password – and the two-factor code when the user has one.
2. Home Assistant sends the browser back with a one-time code. Family Quest exchanges it **itself** (server side,
   inside Home Assistant on the Supervisor network: `http://homeassistant:8123`; with https in Home Assistant at the
   address below), asks Home Assistant who the user is (websocket `auth/current_user`) and **revokes the Home
   Assistant tokens right away** – Family Quest stores no Home Assistant token and no password, only the profile login
   as with a PIN.
3. The Home Assistant user is mapped to the profile linked with it (Profiles › edit › *Home Assistant user*):
   a child gets its app, a parent gets the same as a parent PIN login in the app.
   The parent area on the app port stays as before – with *Parent area only through Home Assistant* it stays closed.
   A Home Assistant user that is not linked gets «Your Home Assistant user is not linked with a profile – ask your
   parents». Every attempt is in the login log; the login stays on the device like a PIN login, *Log out* as usual.

**🔐 Sign-in per profile:** every profile has exactly one sign-in, chosen in Profiles › edit (top of the *Profile*
tab) and shown as a chip on the profile cards:

| Sign-in | Who | How | Needs |
|---|---|---|---|
| 🪄 **No sign-in – tap the profile** | children only | tap the picture and in | – |
| 🔢 **PIN** | all | picture or digit PIN (children), 4–8 digits (parents) | a PIN |
| 🏠 **Home Assistant only** | all | Home Assistant sidebar, *Sign in with Home Assistant* on tablets | a Home Assistant user |
| 🔢🏠 **PIN or Home Assistant** | all | both ways | a PIN and a Home Assistant user |

The Home Assistant user picker shows only for the two Home Assistant options (picking a user fills in the name), the
PIN entry only for the two PIN options (an existing PIN stays; *Change PIN* sets a new one). Saving checks it (also
on the server): Home Assistant options without a user, PIN options without a PIN, and *No sign-in* for a parent are
refused. What a choice does not use is removed when it is saved – *No sign-in* and *Home Assistant only* delete the
PIN, *No sign-in* and *PIN* unlink the Home Assistant user – so nothing hidden stays a way in.

The server enforces the choice on every way in: the app's PIN login and tap login, the picture PIN, the parent-area
PIN, the automatic login in the Home Assistant sidebar (children and parents) and *Sign in with Home Assistant* in the
app. *Home Assistant only* refuses every PIN (also a PIN left over in an old database), *PIN* refuses every Home
Assistant login, *No sign-in* exists only for children. A child with *No sign-in* that sets a PIN itself (Me › *Change
my PIN*) switches to *PIN*; a child with *Home Assistant only* cannot set a PIN itself. Linking or unlinking the own
Home Assistant user in the parent area (*Link my user* / *Unlink*) switches a parent between *PIN or Home Assistant*
and *PIN*.

The app's profile list shows a small icon per profile (🔢 / 🏠 / 🔢🏠, nothing for *No sign-in*) and routes the tap:
*No sign-in* straight in, *PIN* the PIN pad, *Home Assistant only* straight to *Sign in with Home Assistant* (in the
Home Assistant sidebar: the own Home Assistant user), *PIN or Home Assistant* the PIN pad with the Home Assistant
button. Parents appear there only when they can sign in on that device.

**Profiles from before** get their sign-in once at the first start of the update, from what they had: PIN and Home
Assistant user → *PIN or Home Assistant*, PIN → *PIN*, Home Assistant user → *Home Assistant only*, nothing → *No
sign-in* (children). Nothing else changes. A parent without both (should not exist) gets *PIN* and needs a PIN at
the next edit.

**Home Assistant address for the sign-in:** the browser of the tablet must reach Home Assistant. Empty = automatic:
the host of the app with the port of Home Assistant (the add-on runs on the Home Assistant machine, e.g.
`http://192.168.1.10:8123`; https when Home Assistant does https). Enter another address when Home Assistant is
reached differently (a name with a certificate, a reverse proxy); the addresses Home Assistant knows itself
(internal / external URL) are offered. *Test* checks both ways: this device → Home Assistant and Family Quest →
Home Assistant. Limits: the device needs to reach Home Assistant (not from a guest network that cannot); Home
Assistant's login page is shown in Home Assistant's look and language; the state of a sign-in is valid for 10
minutes and once; IP bans and login attempts of Home Assistant apply as usual.

**One port for the children, the parent area only in Home Assistant:** no second port is needed. Home Assistant
reaches the app through its own way (ingress, from the Supervisor), the app port (e.g. `http://192.168.x.y:8099`)
is for tablets and phones. With *Parent area only through Home Assistant* switched on, the app port offers no parent
area at all: the link is gone, `/parents` only shows a hint, and every request of the parent area that does not come
through Home Assistant is refused – even with an old session.

**Look:** the parent area uses the shapes of Home Assistant (Roboto, flat cards, the HA sidebar) with the colours of
Family Quest (as in the chore planner); opened in Home Assistant it follows the light or dark mode of the HA theme.
Buttons that add something («+ Add child», «+ New topic», «+ Add account» …) are always top right.

**Parents and their Home Assistant user:** in the profile of a parent you choose the Home Assistant user (all persons of
Home Assistant with a login) – sign-in *Home Assistant only* or *PIN or Home Assistant*. With it the parent area
opens in the HA sidebar without PIN. The PIN (*PIN or Home Assistant*) is the login in the app, e.g. to join a game or
learn along on another device. A parent with *Home Assistant only* appears in the app's profile list only while *Sign
in with Home Assistant in the app* is on (tapping it opens the Home Assistant login). Without Home Assistant parents
need a PIN as before.

**Children and their Home Assistant user:** children who have their own Home Assistant user open their app in the
Home Assistant sidebar without PIN as soon as the user is chosen in the child's profile (Profiles › edit › *Home
Assistant user*) – there is no extra switch (the former option *Children may sign in with their Home Assistant user*
is gone; existing links stay and now simply work). One Home Assistant user belongs to at most one profile – parent or
child. A child without a link logs in with its PIN.
- In the sidebar it works through Home Assistant (ingress): the user is only trusted on requests from the Supervisor
  proxy. On the app port (tablets) the child uses its PIN – or *Sign in with Home Assistant* when that is switched on.
- The child only gets the children's app – never the parent area. *Parent area* from there asks for the parent PIN.
- *Log out* (or the automatic log-out after a break) ends the login in that tab without logging in again right away;
  the profile screen then offers *Log in as …* for the child's Home Assistant user. Reloading keeps the tab logged
  out; opening Family Quest anew (a new tab) logs the child in again.
- Archived or deleted children, block times, OfflineTime and the network filter apply as with a PIN login.

**The panel for every Home Assistant user:** the Family Quest panel in the sidebar is visible to all Home Assistant
users, not only administrators (`panel_admin: false`), so children with their own (non-admin) user can open it. What
opens depends on the user: the parent area for parents linked with their Home Assistant user and for Home Assistant
administrators; for everybody else (not linked, not an administrator) the children's app with the normal profile
and PIN screen – a linked child (option above) is logged in there directly. The parent area itself still needs the
parent PIN or a linked parent Home Assistant user. If Home Assistant cannot tell whether a user is an administrator,
the children's app opens; *Parent area* there leads to the PIN login.

- **Overview › Failed logins:** every wrong PIN of the last 30 days with time, profile, IP address, MAC address and
  device name (from the UniFi device trackers in Home Assistant, when available) and who normally logs in
  successfully from that address. Requests refused by the network filter are listed as well.
- **Settings › Access from the network:** the networks (e.g. `192.168.35.0/24`) from which the app may be used, and –
  stricter – from which the parent area may be opened (e.g. only the parents' network). Empty = every network.
  A list that would lock out the device you are saving from is refused.

## Family (parent area, formerly «Community»): family quiz and family council

- **Family quiz** (learning app › Family › Quizzes, or parent area › Games): everybody – children too – makes
  quizzes (2–4 answers, one right, time per question) or copies a template (Swiss waters, geography of Europe,
  capitals of Europe and the world, flags, food of the world, Swiss specialities, cantons, animals, space,
  inventions, Switzerland). Whoever starts a game leads it (a parent may always step in); everybody joins on their
  own device. Quick right answers give more points (1000 down to 500). Places go into everybody's history; the
  reward events *Played the family quiz* and *Won the family quiz* can give coins (Rewards › Rules).
- **Family Quest Facts** (special quiz – «New quiz» › 📊 at the top, for children and parents): the questions come
  from the family's own Family Quest data and are made new at every start – a random choice in a random order, at most
  one question per kind. Before the start: the number of questions (5 / 10 / 15 / 20) and the focus (this week, all
  time or mixed). It is played like every family quiz (multiple choice and estimates, the same points and rewards)
  and is multilingual: the questions come in the starter's language (German: Swiss German with «Ämtli» or Standard
  German with «Aufgaben», like the app) and everybody can switch to another language in the game.
  About 60 kinds of questions: chores today / this week / last week / of all time (who of the children, how many),
  XP, levels, streaks, coins earned this week, badges, learning time and lessons, games played this week / last week /
  in the last 7 days / in all, the most popular game, who wins the most games (also «a guest»), family quiz and chess
  wins, the last family game, records (Jump, Star Runner, Snack Rush, Traffic Cadet, Clap the Beat, Five Dice, 24h Endurance: most laps and the
  fastest pit stop), the
  slot machine, the shop (things bought, coins spent, the shopping queen or king, the favourite reward, avatar
  items, pranks), pets (how many, who has the most, who lost the most, the oldest, the most common kind, babies, coins
  of the hamsters, whose pets are cared for best – the average of the care bars of the pets at home), bulletin board
  notes, polls, family council, quizzes, Wichteln, FamilyTime, the next birthday in the calendar, guests, own flash
  cards. A question is only asked when its data is there and the answer is clear: «who of the children» needs at
  least two children, a tie is never asked. Wrong answers are the other family members (or nearby numbers);
  estimates go from 0 to a round number above the answer.
  Privacy: only things the family sees of each other anyway – nothing from the parent area (no internet times or
  logs, no mood or behaviour weather, no login log). XP, levels, coins and learning time only when the family view
  shows «Everything» (Settings › Family view). Parents switch the special quiz off in parent area › Games › Family
  quiz › Settings (on by default).
- **Bingo** (learning app › Family, or parent area › Games): whoever starts sets the rules (speed, one line /
  two lines / full card – the rules used last are the default); everybody joins with a 5 × 5 card (B-I-N-G-O, 1–75,
  free star). A ball carousel spins, stops and shows the new ball for about 5 seconds. Players mark the numbers
  themselves and press «BINGO!» – the app checks it; a false «Bingo!» blocks the button for 10 seconds. Everybody can
  show the rules any time (📜).
- **Family council** (learning app › Family): anybody asks the family something, everybody adds ideas, then the vote
  starts – secret, one vote each, changeable until the vote ends. The result goes into the history of everybody who
  took part.

### Polls

Below the family council: **📊 Polls** – a question with 2 to 12 answers, one or several answers allowed,
anonymous or with names, optionally with a closing time. Everybody sees the result after answering; who asked (or a
parent) can close or remove the poll. A banner on the start page reminds who has not answered yet.

### Bulletin boards (Schwarzes Brett)
Under the polls: **📌 Bulletin boards** – endless pin boards, one per topic («Summer holidays», «Birthday party», …).
Everybody of the family makes boards (title + emoji) and works on every board; guests (QR invitation) never see them.
Who made a board, or a parent, renames, **archives** (still readable, no more changes) or removes it with **⋯**.

A board opens full screen (✕ closes it):
- **Pan** with one finger or the mouse on an empty spot, **zoom** with two fingers, the mouse wheel or **+ / −**
  from 5 % to 400 %; **⤢** shows everything. The last view of each board is remembered on the device.
- **🗒️ Sticky note** in 8 colours: choose a colour, tap the board, write. **🔤 Text** in 8 ink colours (A− / A+ for
  the size). **✏️ Pen** with 8 colours and 3 widths, **🔷 shapes** (rectangle, ellipse, arrow, line), **🧽 eraser**
  (wipe over lines and shapes).
- **👆** moves items, a tap selects one (write, colour, bring to front, remove, the round handle resizes notes and
  texts), a double tap writes. Every note shows who made it. **↶** undoes the own last steps (also Ctrl+Z; Delete
  removes the selected item).
- **Live:** changes of the others appear within about a second; the avatars at the top show who is on the board (tap
  one to jump to what they see), their pointer appears with their name, and an item somebody is moving or writing has
  an outline in their colour. Last change wins per item.
- A badge «New: n» on the board list and a banner on the start page show what the others changed since you last
  looked.

Limits: 200 boards, 2000 items and about 3 MB per board, 1000 characters per note, 2000 per text, lines are thinned out
to 600 points. Everything is in the database, so the backup contains the boards.

### 📚 Library: the family bookshelf (books, interactive books) – and the adventure games
In the app menu **📚 Library** (formerly «My books»; also a card on the Family page) and in the parent area under **Family**: children and
parents write books, the whole family reads them. Guests never see them. The library shows two **book types**, shown as
a badge on every cover and row and as a filter above the shelf (📚 All · 📕 Books · 📖 Interactive books). The third
type, the **🗝️ adventure games**, is stored the same way (table `story`, type `game`, same API `/api/stories`) but lives
under **Games**: in the kids' app a card «🗝️ Adventure games» on the games page (below the family quiz) opens their own
shelf (`#/advgames`: play, continue, own drafts, 📥 Import and + New with the templates); in the parent area under
**Games › 🛠️ Custom games › 🗝️ Adventure games**. They are a game of their own in the games settings (key
`adventuregame`: active / inactive, for everybody or chosen children – no bots, no price): switched off for a child (or
while the child may play no games: game time used up, OfflineTime, block time), the server hides the adventure games
from its shelf and refuses reading, playing, writing, creating and importing them («Adventure games are switched off
for you»); parents are never bound. A family that never set it keeps them open after the update (not switched off like
a really new game).
- **📕 Book** (picture book) – pages with a picture and a text, read page by page (below).
- **📖 Interactive book** (formerly «adventure book», type key `adventure`) – reads like a book; at a few pages the
  reader chooses how it goes on; one or several endings (all may be happy), items (below).
- **🗝️ Adventure game** – point & click games: rooms, hotspots, items, switches, dialogues and endings (below).
Visibility (🔒 / 🧒 / 👨‍👩‍👧), approval, rewards, ⭐ ratings, reading progress, the parent area and the privacy rules are
the same for every type. **+ New book** first asks for the type; a new book of any type is for the **👨‍👩‍👧 whole family**
(changeable right there and in the editor – with approval on it still waits for a parent once published).

#### 🎨 Own drawings (the drawing editor)
Every book type draws its own pictures with one **vector drawing editor** (`web/svgpaint.js`) – the pictures are
**SVG**, not pixels, so they stay sharp on every screen and stay small:
- **Tools:** 👆 select & move · ✏️ pen (smoothed strokes, 4 widths, stylus pressure) · ╱ line · shapes (▭ rectangle,
  ⬭ ellipse, ◯ circle, △ triangle, ⬠ polygon – tap the corners, tap the first one again to close) · stamps (⭐ star,
  ❤️ heart, 🌳 tree, ☁️ cloud, ☀️ sun, 🏠 house, 🚪 door, 🪟 window – drawn as paths) · 🔤 a word of text · 🪣 fill (the
  tapped shape gets the colour; tapping the background colours it) · 🌄 background (white paper, sky, meadow, grass,
  sea, beach, night, sunset, room, cave, snow, space – gradients – or see-through). 16 colours plus an own colour,
  outline on / off for shapes.
- **A selected shape** has handles: the big corner scales, the side handles stretch, the yellow one above rotates
  (snaps to 45°); drag to move. The floating bar: 🗑 remove, ⧉ duplicate, ⬆ ⬇ layer, ↻ straighten. ↶ ↷ undo / redo
  (also Ctrl+Z / Ctrl+Y, Delete). Picking a colour with 👆 recolours the selected shape.
- **Finger and stylus:** one finger draws, **two fingers zoom and move the picture** (never the page; ⤢ shows the whole
  picture again). The toolbar is compact (phone 390×740 without scrolling, tablets with a larger picture), light and
  dark mode.
- **Two kinds:** a **scene** that fills a page or a room (viewBox 800×600, 4:3, max. **60 KB**) and a **thing / a
  character** (200×200 with a see-through background – it stands in the scene; max. **20 KB**). A meter shows the size;
  ✓ *Use picture* sends it to the server, which cleans it (`svgsafe.py`) and gives back what the book keeps.
- **Editing again:** the SVG is its own shape model – every shape is one element with `translate() rotate() scale()`
  and the picture is marked `id="fq-draw"`, so ✏️ *Change drawing* opens it shape by shape. A picture from somewhere
  else (SVG code, an AI) opens as one locked layer to draw on top of.
- **Stored in the book:** a drawing is cleaned SVG text inside the book data (`{"k": "svg", "v": "<svg …>"}`), not a
  separate file – so it has exactly the privacy of its book (a 🔒 private book's drawings reach nobody else, parents
  neither: no endpoint returns them), it is part of every backup (the database), and it goes along in the export.
- **Where:** 📖 page picture (thing) and page background (scene); 📕 page pictures and the cover (scenes); 🗝️ room
  backgrounds and variant pictures (scenes), hotspot and item pictures (things, placed on the room like the shipped
  assets); the shelf shows drawn covers (the first page, the cover, the start room).
- **Older painted pictures** (PNG files of the earlier painter) are still shown everywhere and can be replaced by a new
  drawing; photos stay files as before.

#### 📕 Books (picture books)
- A **cover** (picture, title, author – the title and the colour are set in ⚙️) and up to **60 pages**. Every page has a
  **layout**: 🖼️ *picture on top* (text below), 🌄 *full-page picture* (the whole picture edge to edge, the text lies on
  its lower edge – on tablets on the picture) or 📝 *text only* – and a text (max. 600 characters).
- **Picture** per page: 🏞️ one of the 24 shipped scenes (`web/img/stories`), 😀 an emoji, 🎨 an own drawing (the
  drawing editor, a scene), 📷 a photo (same upload rules, max. 2 MB) or **</> SVG code** (e.g. from an AI).
  SVG pictures are **cleaned strictly on the server** (`svgsafe.py`): only drawing elements (path, circle, rect,
  polygon, g, gradients, clip paths, short text) and presentation attributes survive; `script`, `foreignObject`,
  `image`, `use`, `style`, links/`href`, `on…` handlers, external `url(…)` references are removed, a DOCTYPE / entity or a
  file that is not an `<svg>` with a viewBox is refused; max. 60 KB per picture. The app shows them only as an image
  (`<img>` data URL), where nothing can run.
- The editor (phone and tablet): cards for the cover and every page with the layout switch, ↑ ↓ to move, 🗑, a
  character counter; the checker lists pages without text or without picture. ▶ reads the draft.
- **Reading:** the cover, then page by page – ◀ ▶ buttons, swiping with the finger or the arrow keys, page counter and
  dots; book typography; «The end» with ⭐ after the last page. The shelf shows «Page 3 of 12» / «▶ Continue» and
  «✅ Read». Reaching the last page counts as reading it to the end (reading reward, ratings).
- **Sample book:** «Klonk, the laziest dwarf in the mountain» (12 pages with own SVG illustrations, author
  «Family Quest») is on the shelf for the whole family, in the language of the app (all 10 languages, Swiss German in
  Zürich dialect). Nobody can change it; parents hide it (parent area › ✨ Sample books, or ⚙️) and show it again –
  progress and ratings stay.

#### 🗝️ Adventure games
Point & click games that the family builds and plays (`adventuregame.py`, `web/adventure.js`). **+ New** (Games › 🗝️ Adventure games) – the templates first:
an empty game or a template – 🧙 «Escape from the wizard tower», 📦 «The secret of the attic», 🚀 «Lost in the
spaceship» (4–5 rooms each, small and solvable, with items, a dialogue, a combination and a funny 💀 ending; in all
app languages, Swiss German in Zürich dialect).

**Building** (the editor, phone and tablet; tabs 🗺️ Map · 🚪 Rooms · 🎒 Things · 💬 Dialogues · ⚙️ Rules):
- **Rooms:** a picture – one of 10 own room scenes (tower room, library, stone hall, hallway, dark room, spaceship cabin /
  corridor / bridge, engine room, storage room) or the 24 scenes of the books, an own drawing (drawing editor), a photo or SVG
  code (cleaned like the picture books) – and a description. ⭐ marks the start room; ▶ tests from any room.
  **🔀 Changes when …**: up to 3 variants with another text / picture while a condition holds («the light is on»).
- **Hotspots** (max. 30 per room): ✏️ *Draw hotspot*, choose the kind and drag a rectangle over the thing on the
  picture (finger or mouse; a tap makes a standard box). Tap to select, drag to move, the round handle resizes –
  positions are percent of the picture, so they fit every screen. The sheet below: kind, name, a picture on the
  hotspot (39 own SVG things and characters – doors, keys, chest, lever, lamp, candle, book, potion, rope, stick,
  ladder, crystal, magnet, battery, cable, key card, button, screen, cauldron, bookshelf, table, bed, box, plant, well,
  magic wand; wizard, robot, cat, dragon, ghost, knight, pirate, alien, owl – an emoji, an own drawing (a thing with a
  see-through background), or invisible over the room picture), the look text, «Visible only when» (conditions) and the use rules.
  - 🚪 **Door:** leads to a room or straight to an ending; optionally «Opens only when» (an item, a switch) with a
    locked text. «＋ New room» makes the room with a door back.
  - 📦 **Object:** can be taken (becomes an item; it disappears – or 📦 *stays in the room* and gives its item once,
    e.g. a chest with a key).
  - 🧙 **Character:** talks – the first dialogue line.
- **🎒 Things:** items (name, picture; max. 60), 🚩 switches (things the game remembers; max. 100), 🏁 endings
  (🏆 win / 💀 lose with their text; max. 20). Removing one removes every reference to it.
- **💬 Dialogues** (max. 200 lines): a line is what the character says; up to 6 answers, each with an optional
  condition, actions and the next line (or the end of the talk). 👋 Leave always works.
- **⚙️ Rules** (max. 200): 🔧 *use* an item on a hotspot («key → chest») or just use a hotspot («pull the lever»),
  🧪 *combine* two items («stick + rope = fishing rod») – with conditions and actions. The first rule whose
  condition holds wins. A key on a locked door needs no rule (the door opens when its condition holds).
- **Conditions** (max. 4, all must hold): has / has not an item, a switch is on / off. **Actions** (max. 8): show a
  text, give / take away an item, switch on / off, go to a room, end the game.
- **🗺️ Map:** rooms as boxes (rows by distance from the start room), doors as arrows, 🔒 dashed arrows for locked
  doors, 🏆/💀 for doors to an ending; tap a room to edit it.
- **The checker** (on the server, after every automatic save): rooms without name or description, doors leading
  nowhere, hotspots without name, objects without item, characters without dialogue, a door whose key can never be
  obtained, items nobody gives, switches that are needed but never switched on, things that do not exist any more
  (deleted item / switch / room), dialogue dead ends (no answer that always works), incomplete rules, no way to a 🏆
  ending, rooms no door reaches. Then it **plays every way through the game** (a breadth-first search over room,
  backpack, switches, taken things and dialogue line; max. 6000 states / 1.5 s): «the game cannot be won» stops
  publishing; hints (💡, do not stop publishing): rooms that are never reached in play, dialogue lines never said,
  «players can get stuck in …» (a state from which no way leads to a win any more – they can start again), «too big to
  test every way». Drafts are saved incomplete; 🚀 needs a game without errors.

**Playing:** the room picture with the hotspots on top (🔍 shows everything you can tap), below the verbs of the
tapped thing (👁️ Look at, ✋ Take, 💬 Talk, 🚪 Go through, 🔧 Use – only the ones that make sense), the messages and
the room description; at the bottom the 🎒 backpack: tap an item, then a thing in the room («use with») or another
item (combine). Dialogues show the character, the line and the answers. Endings: 🏆 / 💀 with their text, «2 of 3 endings
found», ⭐ rating (not for the own game), ↺ play again. The game runs **on the server** (the player never gets the
hidden hotspots, rules or the solution, moves are checked), every player's game is saved (▶ Continue on the shelf,
↺ start again). ▶ in the editor and 👀 for a game waiting for approval play the working copy without saving.
Phone 390×740 without scrolling, tablets with a larger picture.

**Import / export:** `family-quest-adventuregame/1` (instructions and a field guide for an AI, the background and asset
ids, `_svg_rules` for own drawings and the wizard tower as a full example – with a drawn room and a drawn item). Readable ids in the file (`room1`, `spot3`,
`item2` …), conditions as `item:key` / `!flag:light`, actions as `{"give": "key"}`. The import is tolerant (code
fences and sentences around the JSON, comments, trailing commas, items and switches only named in a hotspot, other
spellings of actions) and checks everything again; games come in as private drafts. Own drawings go along as inline SVG
(`"background": {"svg": "<svg …>"}`, `"picture"` / `"icon": {"svg": …}`), cleaned again on import; photos stay out of
the file. Limits: 40 rooms, 30 hotspots per room, 60 items, 100 switches, 200 dialogue lines, 6 answers, 200 rules,
20 endings, 2 MB per game.

#### 📖 Interactive books

**Writing** (✏️ Edit, or **+ New book**: title, language, an empty book or a template – 👸 «The princess who didn't
want to marry» (marry the prince as a friend first, become a dragon tamer or open a bakery – three happy endings),
🦊 «The little fox's birthday» (for the youngest: which friends, which cake – three happy endings), both 13–14 pages
with exactly two branch points; and the older choose-your-path stories 🌴 jungle with the lion, 🚀 space, 🏰 haunted
castle, 🐠 underwater – each a small finished story in all app languages, de-CH in Zürich dialect):
- A book is a list of **pages**: 📄 **scene**, 🏆 **good ending** (confetti) or 💀 **bad ending** («Try again»; optional –
  every ending of a book may be a happy one). Each scene has a switch: **➡️ Goes on** (a linear page: one next page,
  `next` – the reader taps «▶») or **🔀 Choice** (a branch point: 2–4 choices A–D, each pointing to another page). Most
  pages of a book simply go on; new scenes start as «goes on». **+ Next page** on a page that goes on makes a new
  linked page right after it (it takes over the old next page and the background). Paths may merge or go back to an
  earlier page. In the target list «＋ New scene / good ending / bad ending» makes the page right away. Every page
  carries its **number in a purple circle** (page cards and map), and next to the target list the same purple circle
  shows the number of the page it leads to. Books of older versions (every scene with choices) stay as they are.
- **Picture** per page: an emoji, an **own drawing** (the drawing editor above – a thing with a see-through
  background) or a **photo** (made smaller in the browser, max. 2 MB per picture).
- **🏞️ Background** per page: 🎨 an **own drawn background** (a scene of the drawing editor), one of 24 own scenes
  (jungle, beach, deep sea, space, haunted castle, enchanted forest, snowy mountains, desert, pirate ship, crystal cave,
  city at night, village, dragon's lair, candy land, dinosaur valley, volcano, North Pole, mine, castle in the clouds,
  train station, school, kids' room, attic, laboratory – small SVG files in `web/img/stories`) or none; the picture
  sits on top of it, the text stays on the paper below.
- **🎒 Items:** a scene can give one item («🍌 Banana»); a choice can need one – readers only see it when they have it.
- **🃏 Pages / 🗺️ Map:** the map shows every page as a box (rows by distance from the first page): thin arrows for
  pages that go on, arrows with the letter A–D for the choices (🔀 marks a branch point); dashed arrows need an item, red stubs are choices without a target, orange boxes need work, dashed boxes
  cannot be reached. Tap a box to edit the page.
- The **checker** lists what is missing: a page that goes on without its next page, a branch point without
  continuation or with only one choice, choices without target or text, no good ending (one ending is enough), pages
  that cannot be reached, pages from which no path leads to an ending (endless loops), an item no page gives, a branch
  point where every choice needs an item. Drafts are saved automatically (also incomplete); **🚀 Publish** needs a complete book. **▶ Try**
  reads the draft right away (nothing is saved).
- After publishing, further changes stay in the draft until it is published again – readers see the published version.

**Reading** (tap a cover): like the book reader – the picture across the width, the text in book typography (long text
scrolls inside the page, the screen itself does not scroll), at the bottom ◀ «Page n» ▶ in reach of the thumb (also
swipe and the arrow keys). ▶ turns a page that goes on; on a branch point the choices sit as big buttons right above
◀ ▶. ◀ goes back to the page actually read before (the server keeps each reader's path, `story_read.state`, with
the backpack of then; endings found stay found). ⏮ back to the start, 🎒 the backpack. Phones on their side show the
picture left and the text right. Every reader collects their own endings («2 of 5 endings found» on the cover) and gives ⭐ 1–5 after reaching
an ending (not for the own book).

**Who can read it** (chosen by the author when the book is made and in the editor at any time; new books: 👨‍👩‍👧, imported
books: 🔒):
- **🔒 Only me** – only the author can read it, parents neither. Nobody else gets its title, text or pictures from the
  app; in the parent area parents only see that a private book exists (author, page count, date) and cannot open,
  change or remove it. Never needs approval. Limits of this privacy: the history of coins / XP keeps the title of a
  book that once paid a reward (only books the others could read pay – made private later, the entry stays), and
  backups of Home Assistant / the app (`/data/family_quest.db`) contain every book, private ones too – whoever has a
  backup can read them. Deleting a profile for good removes its books too.
- **🧒 Other children** – all children of the family (and the author). Parents see these books only in the parent area
  (moderation: read, edit, unpublish, remove).
- **👨‍👩‍👧 Whole family** – children and parents.

**Import / export of picture books:** the same, with the format `family-quest-picturebook/1` (instructions for an AI,
`_svg_rules` – how to draw safe inline SVG: viewBox 800×600, simple flat shapes, own background, max. 60 KB, no scripts or
external files, little text –, the library ids and the sample book as an example). Pictures go along as SVG (own drawings
included), library id or emoji; photos stay out. A file may contain picture books and adventure books together; every book
comes in as a private draft.

**Import / export** (same idea as the quiz and pack files for an AI): ⚙️ › **Export as a file** saves a book as
self-describing JSON (`family-quest-story/1`: instructions, field guide and `_svg_rules` for an AI, the background ids,
the book with pages, `next` (the page that follows a page that goes on – files without it still import), choices, endings, items, emoji pictures, own drawings as inline SVG (`"picture": {"svg": …}`,
`"background": {"svg": …}`) and backgrounds – photos stay out; the template for the AI is the fox book: mostly linear
with two branch points and three happy endings, with a drawn page background and a drawn thing as examples). **📥 Import** on
the shelf: copy the **template for the AI** into any AI chat, describe the idea, paste the answer (sentences and code
fences around the JSON are fine) or choose a file. Every book comes in as a private draft of whoever imports it (ids,
authors and anything else from the file are not taken over), the checker shows what is still missing. Every drawing
is cleaned again (`svgsafe.py`); a drawing that is too large (things 20 KB, scenes 60 KB) or not usable is left out.
Max. 4 MB, 5 books per file.

**Single-language books:** a book is written in one language (a language tag, chosen when it is made, changeable in ⚙️)
– there are no translations inside a book. The templates come in every app language.

**Parents** (Family › Library › ⚙️): the bookshelf on/off per child (off: no menu entry, no reading or
writing), **approval** before the others see a child's book (default off – then a book for 🧒 / 👨‍👩‍👧 waits under
«Waiting for approval»: 👀 read, ✓ approve, ✗ back to a draft; a new version waits again while the readers keep the
approved one), rewards for writing: coins / XP per book (default 20 coins, paid once per book when the others can first
read it – not for private books) and per reader who is somebody else and reaches an ending for the first time
(default 0, once per reader). Parents edit, unpublish and remove every book that is not private; children edit their
own.

Limits: 300 books (sample books not counted; 60 per person), 200 pages per adventure book, 60 per picture book, 40 rooms per game (600 characters per
page); own drawings and SVG pictures: scenes 60 KB, things 20 KB each, 2 MB per book with everything; adventure books: 1500
characters per page, 120 per choice, 40 per item, 80 per title; photos max. 2 MB each and 300 MB together (in
`media/_stories`, part of the backup; pictures no book uses are removed).

### Wichteln (secret gift giving)
Under the polls, everybody can start a **Wichteln**: enter the occasion (e.g. «Christmas 2026»), choose who takes part
(whole family or single members) and the rules – *parents not among each other*, *children not among each other*, or
nothing ticked for completely open. On **Draw** the app draws at random who gives a present to whom (never to
oneself). Everybody sees only whom **they** give to – behind a «Show» button, so nobody looks over the shoulder. The
whole list is shown to nobody, not even to who made it. Who made it or a parent can delete it.

With a **date**, every participant gets a to-do in the Family Planer («🎁 Wichteln: occasion · 24.12.» – without the
name of the receiver, the planner may hang on the wall). Tick it off in the planner or with **Present ready** in the
Wichteln card – both count. Deleting the Wichteln removes the open to-dos.

The parent menu has **📝 Release notes** below «Log out»; the version number there opens the add-on page in Home Assistant.

### Texas Hold'em

Community → **🃏 Texas Hold'em**: everybody plays on their own device (guests too), **only with play chips** – they
have nothing to do with coins or points. Who opens the table sets the rules (remembered for the next game): start
chips, small and big blind, ante, blinds doubling every N minutes, time per move (then the app checks or folds),
players at most, and the mode: **everybody starts with the same chips** (who has none is out, the last one wins) or
**game leader with a bank** (players ask for chips, the leader gives a buy-in; with a limit of re-buys).
No-limit rules with side pots; heads-up the dealer posts the small blind.

### Texas Hold'em alone against bots

Family › Texas Hold'em › **🤖 Alone against bots**: 1–5 animal bots (easy, normal, hard), start chips and blinds –
the cards are dealt right away, on your own table (the family table stays free). The bots decide by the strength of
their cards and the pot odds; easy bots bluff and call more often. When you have no chips left the game is over.

### Errate den Song

Family › **🎵 Guess the song** (or parent area › Games): the game leader chooses a **speaker** of Home Assistant
(a media player that already has a playlist) and the rules – what who buzzes says (artist and title, artist or
title, only one of them), the others judge by majority or unanimous, points to win (e.g. 10) and songs at most (e.g.
40). The app switches shuffle on and only steers the speaker: play, pause, next song.
Everybody has a big **buzzer** on their device; the first one stops the song and says the answer out loud, then
«Show the solution» shows cover, artist and title from the speaker and the others vote 👍 / 👎. Right +1, wrong −1.
«Nobody knows it» shows the solution without points. Guests can join with the QR code.
The game leader turns the speaker up or down (🔉 − / 🔊 +, 5 % each). After a buzz a **countdown** (setting, default
5 s) runs before «Show the solution» can be tapped – first the answer, then the solution.

**Open in the app:** in the parent area every game has «↗ Open in the app» (top right) – the app opens in a new tab,
logged in as this parent, right in the game.

**Ping and brrr:** after the verdict everybody's device plays a game-show sound for right or a buzzer for wrong (own sounds of the app, made by `tools/make_sounds.py`). With «also on the
speaker» (start dialog, on by default) the speaker plays it too – as an *announcement*: speakers that support it
(e.g. Sonos) lower or pause the playlist for a moment and go on where they were; the queue is not changed. The speaker
fetches the sound from the app's direct access (Options › direct access with its port) – without it only the
devices play the sound.

### Own bots

Avatar › **My bots** (top right **+ New bot**): children make their own bots – name, a look (emoji), a colour and how
well it plays (easy, normal, hard). With *Share with the family* siblings can play with it too. In the start window of
Tschau Sepp, Kartenkarussell, Domino and Texas Hold'em (alone against bots) you tap your bots to put them at the table; free
seats are filled with the animal bots.

### Light and dark

The button ☀️ / 🌙 (top right in the app, next to the language in the parent area) switches between light and dark and
is remembered on the device; without a choice the system (or the Home Assistant theme) decides.

### Games per game and person (parent area › 🎲 Games)

The parent area has two pages: **Family** (family council, polls, bulletin boards, Wichteln, history) and **🎲 Games** (every game:
the family quiz, bingo, guess the song, all live games with their start buttons, coins and photo sets, the running
games, and the game corner). A **search field** at the top filters the games by name (and opens the games found); «⚙️ For all games» holds
*All on / All off*, who begins a game and whether guests may join. Every game is a folded section – always folded when
the page opens (a game running just now shows «● running now»).

Right below the running games comes the group **🛠️ Custom games**: the games with the family's own content, all built
the same way – head (icon, name, what it is, how many), a row **📥 Import** and **+ New** (starting with the templates),
the list of what the family has, then «⚙️ Settings» (status, coins …):
- **🎯 Family quiz** – the quizzes (play, edit, delete, export); Import = a quiz file (export or the answer of an AI);
  New = the «New quiz» dialog with the templates and the «Family Quest Facts» card.
- **🧠 Pair Hunt** – the start buttons and the **photo sets** (also used by the pairs game of the game corner); New =
  a preset (👨‍👩‍👧 Family, 🐾 Pets, 🏖️ Holidays, 🎂 Birthdays, 👵 Grandparents, 🏠 Our home – an empty set with that
  name) or an empty set; Import = photos (several at once) or a **ZIP file** (`POST /api/parent/memory/import`: JPEG,
  PNG, WebP, GIF checked by their first bytes, max. 5 MB each, 40 per set, ZIP max. 60 MB) as a new set; ⬇️ on a set
  exports it as ZIP (`GET /api/parent/memory/sets/{id}/export`, also the photos kept in Home Assistant Media).
- **🗝️ Adventure games** – every adventure game of the family as a row (title, author, status draft / on the shelf /
  waiting, who can see it), the ones waiting for approval with 👀 / ✓ / ✗ like in the library, private ones of others
  only as «🔒 Private adventure game» with the author; Import / New like the library (the template for the AI, the
  game templates); the status *active / inactive* (no bots, no price).

Every game has a **status**: *active*, *active without bots* or *inactive* (= off), and while active *for everybody* or
*only chosen children* (tick the children). Parents can always play – and are not bound by «without bots» either.
Switched-off games disappear from the children's app.

**Active without bots** is offered for the games that can be played with bots: Texas Hold'em, Tschau Sepp,
Kartenkarussell, Domino, Paarjagd, Kartenlauf, Fünf Würfel, Heimwärts, Jump, Snack Rush, Klatsch den Beat, Jass, Werwölfe, Chess,
Dorfmarkt, Beat the Bureaucracy, Tic-Tac-Toe and Ping-Pong. Then the app hides «alone against bots», the bot fields of the start dialogs and
the games against the app, and the server refuses every start with bots («Playing with bots is switched off for this
game»): family tables get no bots (Kartenlauf plays with the people there, Jass needs 4 people, Werwölfe needs 5), chess
only against the family or two on one device, Ping-Pong doubles only with people. Jump, Snack Rush and Klatsch den Beat can still be
played alone, without practice bots. A table where a parent plays along may still be filled with bots.
Stored per game in the setting `games_access` (`{"mode", "profiles", "bots"}`, `PUT /api/parent/games`).

**Price for children** (each game's «⚙️ Settings» block, below the status): a game can cost coins for the children –
parents always play for free.

- **Defaults** (where the parents never set a value for that game): the **quick games for in between** (Pair Hunt, Five
  Dice, Jump, Klatsch den Beat, Star Runner, Snack Rush, Traffic Cadet) rent for **100 coins per week**, the games of
  the **game corner** (Tic-Tac-Toe, Sudoku, Patience, Ping-Pong, Cube solver, One-armed bandit) for **20 coins per
  day**; the one-armed bandit can also be bought for 250 coins; every other game is free. The fields show these values;
  saving the Games page stores what is shown – a 0 set by the parents stays 0 (also after updates).
- **Price for children (coins)** – default 0. With a price, a child buys the game once in the shop and keeps it for
  good, also when the parents change the price later. Back to 0 (and no rent price): free again for everybody.
- **Rent price (coins)** with **Day / Week / Month** (the three are greyed out while the rent price is 0): renting opens
  the game for that child for 1 day, 7 days or 1 calendar month from the moment it pays (31 January + 1 month = end of
  February). Renting again before the end **adds** the period after the current end. Buying makes a rent unnecessary –
  a bought game stays, a running rent is no longer shown. A rent price alone (price 0) means: rent only.
- **The kid shop** has a section **🎮 Unlock games** with every game that has a price and that the parents switched on
  for this child: «Buy: 300 🪙», «Rent: 20 🪙 per week», «bought ✓» or «rented – 3 days left». A confirmation comes
  first; the coins are booked in the ledger (events `game_buy` / `game_rent`) in the same database transaction as
  the unlock – a second tap books nothing (a rent sends the end the app showed; when it changed meanwhile nothing is
  booked). On the **Games page** and in the **game corner** a locked game is a tile with 🔒 and its price; a tap opens
  buying / renting.
- **🎁 Free tries before buying** (0–20, default 1 – only matters with a price or a rent): how often a child may play
  a locked game for free first. A locked tile shows «🎁 1 free try»; the tap offers **Try for free** besides buying and
  renting, the shop lists the tries left. A try is used when the child **starts or joins a table** of a family game
  (alone or with the family; a rematch / «again» is a new try) – once seated, the table can be played to the end and its
  result seen. A game of the **game corner** uses a try when it opens on the try (`POST /api/me/games/try`); closed, it is
  locked again. On the **one-armed bandit** a try is **one spin** (the bet of 1 coin still counts). A second start
  within 10 seconds (double tap, second device) is the same try; the count is checked in one database transaction, so
  parallel requests never use more tries than there are; a start that fails gives the try back. Joining a table a
  parent opened uses no try. After the tries the game is locked as before. Every child starts with 0 tries used.
- **Tables a parent opened**: when a **parent** opens a family table (not alone) of a game that is locked for a child –
  switched off, not bought, rent run out – the child may still **join and play that table**: it shows in the running
  banners, the note «somebody opened a table» and the game's tile («Join»). Starting an own table, alone, a rematch
  stay locked. The daily game time, OfflineTime and block times still count.

Stored in `games_access` per game (`price`, `rent`, `period`, `preview`; `luck` for the one-armed bandit) and per child
and game in the table `game_pass` (`bought`, `rent_until`, `previews_used`, `preview_at`). API: `GET /api/me/games/shop`, `POST /api/me/games/buy`
(`{"game", "kind": "buy" | "rent", "until"}`).

### 🔋 Game battery

Every child has a **game battery** with charge segments – rechargeable, not a tank. Defaults: **5 segments**, every
child (also the existing ones) starts **full**, recharging costs **50 coins**. Parents have no battery and never see it.

- **Starting a game costs one segment**: an own table of a family game (`…/start` – a family table, alone against bots,
  a new round / rematch, a chess game against the family or the bot) and **opening a game of the game corner**
  (Tic-Tac-Toe, Sudoku, Patience, Ping-Pong, cube solver, the one-armed bandit – one segment per opening, not per spin;
  `POST /api/me/games/try`). A duel or a doubles table started inside an opened Tic-Tac-Toe / Ping-Pong costs nothing
  more; **answering an invitation** (a duel, a doubles table) is free.
- **Joining a table somebody else opened is free** – also with an empty battery – and a started game can always be
  played to the end. The family quiz a parent starts costs the children nothing.
- A second start of the same game within 10 seconds (double tap, a second device) is the same start; the charge is
  checked and used in one database transaction, so parallel requests never use more than there is; a start that fails
  (no table opened) gives the segment back.
- **Empty** 🪫: own starts are refused («Your game battery is empty – recharge it or join a table of somebody else»).
  The kid app shows the battery empty and offers **⚡ Recharge · 50 🪙** (a confirmation first): the battery is full
  again, the coins are booked in the same transaction (ledger event `energy_recharge`); not enough coins → an error;
  a second tap finds it full and books nothing.
- **Kid app**: the battery (segments green → orange → red, empty dashed) sits in the header of the Games page with a
  strip «3 of 5 charged · Starting a game costs 🔋1 – joining a table is free», in the game corner and on top of every
  game's card. Unlimited shows «∞ until …». Chores with an energy bonus show «🔋+2».
- **Parent area › Games › 🔋 Game battery** (family default): on/off, capacity (1–20), cost of a recharge (0–10000 coins,
  0 = free), **unlimited energy**: off / permanent / for 1 day / 1 week / 1 month (stored as an until time, shown as
  «∞ until …», **End** stops it), what **reaching the daily goal** does: nothing / battery full / **+N segments**
  (default **+1**), and every child's charge now with **🎁 Recharge** (a free gift of the parents).
- **Per child** (profile dialog › 🔋 Game battery): the same values; an empty field / «as family» uses the family
  default. A child's own unlimited period wins while it lasts (then the family value counts again); «Off» there means
  «not unlimited» even when the family is.
- **⚡ Energy bonus per chore** (chore editor, 0–20 segments, default 0): charged when the chore is done (or approved by
  the parents) – the same moment as its coins –, once per chore task and never above the capacity. The chores of the
  built-in Family Planer have their own model (points only) and no energy bonus.
- Daily goal and chore bonus never go above the capacity; each goal day and each chore task charges once (unique refs
  in `battery_log`).

Stored: setting `battery` (`on`, `cap`, `cost`, `unlimited`, `goal`, `goal_plus`), per child `battery` in the profile
settings (only the values set), the charge in the table `battery` (`charge` NULL = full) and every change in
`battery_log`; `chore.energy`. API: `GET /api/me` → `battery` {`on`, `charge`, `cap`, `cost`, `unlimited`, `forever`,
`until`, `party`, `free`}, `GET /api/me/battery`, `POST /api/me/battery/recharge`; parents `GET/PUT /api/parent/battery`,
`PUT /api/parent/battery/{id}` (`null` / `"family"` = as the family), `POST /api/parent/battery/{id}/recharge`.

### 🎉 Party mode

A switch on top of the parent area's **Games** page and the **overview**. Switching it on opens a chooser:

- **For whom**: all children or chosen children;
- **What**: **🔓 Unlock all games** (every game playable – price, rent and «inactive» do not count, no free try is
  used), **🔋 Unlimited battery** (starting costs nothing) and **⏱️ Also lift limits** (on by default): the daily game
  time, the **game** block times of the internet plan and the game lock of OfflineTime do not apply to games for these
  children (no game minutes are counted meanwhile). The internet itself, learning limits and a block time of the whole
  app stay as they are. Without «also lift limits» every limit stays.
- **How long**: until switched off, 1 h, 3 h, until midnight or 1 day – stored as an until time; it **ends by itself**.

Nothing is bought, rented or charged during a party – when it ends (by itself or with the switch) everything is as
before. The children see a festive banner «🎉 Party mode until 21:00» on the start page and the Games page, the tiles
are unlocked and the battery shows ∞. **🪩 Disco design**: while the party runs for a child, its app switches to the
Disco design – dark background, neon accents, a disco ball in the header and slow, soft coloured light spots (no
flashing; static with «reduce motion»); afterwards the chosen / season design is back by itself. Parents can also
pick the «disco» scene for an own season design. Stored in the setting `party`; API `GET/POST/DELETE /api/parent/party`
(`{"kids": "all" | [ids], "unlock", "battery", "limits", "for": "forever" | "1h" | "3h" | "midnight" | "day"}`); the kid
app gets `party` in `GET /api/me`.

**The children's Games page** shows the running tables on top, then the family quiz, then two groups of small tiles
(icon + name): **🎲 For a game night** (Tschau Sepp, Kartenkarussell, Domino, Jass, Texas Hold'em, Dorfmarkt, Heimwärts,
24h Endurance, Kartenlauf, Werwölfe, Escape Room, Beat the Bureaucracy, Wer bin ich?, Verbotene Wörter, Zeichnen & Raten, Stadt-Land-Fluss, Guess the song,
Bingo, Chess) and **⚡ Quick games for in between** (Paarjagd, Fünf Würfel, Jump, Klatsch den Beat, Star Runner, Snack
Rush, Traffic Cadet, duels for two), and the game corner at the end. A tile with a running table has a pulsing dot; a
tap opens the game's card in a sheet with its usual buttons (family table, alone against bots, join, rules).

### Family council: new topic

**+ New topic** (top right) opens a window: the question, a few words more, the first ideas, the rule of the vote
(simple / absolute majority / unanimous, and «at least one parent and one child») and how it goes on – collect ideas
first or vote right away.

### Card games: Tschau Sepp and Kartenkarussell

Community → **🂡 Tschau Sepp** (Swiss or French cards) and **🎠 Kartenkarussell** (own cards in violet, raspberry,
orange and petrol): shed your cards by suit/colour or value. Play **alone against bots** (animals with their own
name – private) or open a **family table** (with bots if you like, guests via QR code). Who starts sets the rules
(remembered): cards in the hand, rounds, bots and how well they play, the special cards (7 draw 2, 8 skip,
Under/Jack wish, Ace again, 10 reverse; Kartenkarussell +2, skip, reverse, wish, +4), whether draw cards add up,
penalty cards for a forgotten «Tschau»/«Sepp» («Letzte!»/«Fertig!») and the card back. After the last round the
fewest points win.

### Domino

Community → **🁫 Domino**: lay a tile with a matching number on one of the two open ends of the line. Tap a tile in
your hand – if it fits on both ends you choose **◀ left / right ▶**, otherwise it is laid by itself. Play **alone
against bots** or open a **family table** (bots and guests via QR code like the card games). Who starts sets the rules
(remembered):

- **Set:** double-6 (28 tiles) or double-9 (55 tiles – every number 0–9 has its own colour, easy to tell apart).
- **Cuban** (default): double-9, 10 tiles each, teams of two (partners sit opposite: seats 1 + 3 against 2 + 4), no
  drawing – who cannot play must pass. The round winner scores the pips left in **all** other hands, the partner's
  too (the common Cuban scoring).
- **Simple:** double-6 with 7 tiles each (10 with double-9), everybody for themselves unless teams are chosen;
  optionally draw from the boneyard when nothing fits (pass only when it is empty). The round winner scores the pips
  left in the opponents' hands.
- Teams need 4, 6 or 8 players; otherwise everybody plays for themselves.

When nothing fits, the app says so («No tile fits – you must pass») and shows a big **Pass** button; the others see a
«passes» bubble on that seat. The first round starts with the holder of the highest double; later rounds the winning
side starts – with teams any player of that team may lay the first tile. **Blocked** (nobody can play any more): the
side with the fewest pips wins the round (Cuban: scores all pips left, simple: the opponents' pips); a tie gives no
points and the round is repeated with the same starters. The match goes to **100** points (150 or 200 selectable).
Won while the other side still has 0 points: **🏆 Pollona!** – highlighted in the result and on the score sheet.
**📊** next to the 📜 rules opens the score sheet (round, winner, points, domino or blocked, running totals).

### Paarjagd

Games → **🧠 Paarjagd**: the pairs game live – everybody turns the cards on their own device. Play **alone against
bots** or open a **family table** (bots and guests via QR code like Domino). Who starts chooses (remembered): the
cards (the emoji sets or the parents' photo sets from Games › Custom games › Pair Hunt), **6, 8, 12 or 18 pairs**, the bots and
how well they remember cards (easy / normal / hard) and the **card back** (tap one; the family crest when there is
one). On your turn you turn two cards: a **pair** is yours and you go again; **no pair**: everybody sees both cards
for a moment, then they turn back and the next player goes. When all pairs are found the most pairs win – a tie
shares the place. The board always fits the screen, also on a phone.

**Coins for places 1–3:** the parents set them in Games › Paarjagd («🪙 Coins for place 1 / 2 / 3», default
10 / 5 / 2). They are paid once at the end of a game, and only at a **family table with at least two people of the
family**: no coins alone against bots, none for guests and none for bots. The result shows «+10 🪙» next to the place.
The existing Pairs game in the game corner (one device, take turns) stays as it is.

### Wer bin ich?

Games → **🎭 Wer bin ich?**: the guessing game live – everybody on their own device. Who opens the **family table**
chooses a category (animals, jobs, food & fruit, countries, Swiss places & mountains, fairy tales & legends, things at
home, sports, famous people – every device shows the characters in its own language, and «I am …» counts in every
language of the players at the table). Only people play: the family
and guests via QR code – no bots, and at least two players. At the start everybody gets a different character at
random. Each device shows the characters of **all the others**; your own stays «❓» until you found it or gave up
(the server never sends it to you before).

It goes round in seat order (finished players are skipped). On your turn you can:

- **ask a yes/no question** – type it or just say it aloud, then «Ask question». The others answer ✅ yes / ❌ no /
  🤷 don't know (finished players too – they know). When all have answered the question closes; the asker (or who
  leads) can close it earlier once there is an answer. A **majority of yes**: you ask again; otherwise (no, don't know,
  a tie) the next player goes.
- **guess** «I am …» – checked against the name and a few other names (no matter capitals, umlauts / accents,
  articles, punctuation; one typo is fine from 5 letters, two from 9). Right: you are finished and get the next place
  (a short reveal for everybody). Wrong: the next player goes.
- **give up** («🏳️», any time, with a confirmation) – your character is shown, you are finished without a place.

Everybody sees the open question with the live counts and the last answered question; «My questions» lists your own
questions with their answers. The game ends when everybody is finished; who leads can also pass the turn on (⏭, e.g.
somebody left) or end the game at any time – then all characters are shown and only who found theirs has a place.
The result shows every character, the places and the coins.

**Coins for places 1–3:** set by the parents in Games › Wer bin ich? (default 10 / 5 / 2), paid once, only at a
table with **at least two people of the family** – never to guests. Every person gets a history entry (place, players,
their character).

### Kartenlauf

Games → **🏁 Kartenlauf**: a race board game with cards, played live – everybody on their own device. Play **alone
against bots** or open a **family table** (guests via QR code; bots fill the free seats when the game starts). Who
starts chooses (remembered): **2, 3 or 4 players**, **teams of two** (only with 4; partners sit opposite, on by
default), how well the bots play (easy / normal / hard), their reaction time and two house rules: «a 7 may move the
partner's marbles too» (off: only once your own are all home) and «the joker may be the card that wins» (on).

The board is always the 4-seat board: a ring of 64 fields, every seat with a start field, a kennel with 4 marbles and
4 home fields that branch off just before its start field. Two players sit opposite each other. Every round deals
**6, 5, 4, 3, 2** cards, then again 6 (two French decks with 6 jokers, a fresh deck with every 6); the dealer moves
on each round. With teams, every round starts with each player passing one card to the partner.

- **A** 1 or 11 forward or bring a marble out · **K** 13 or bring out · **Q** 12 · **4** 4 forward or 4 backward ·
  **2, 3, 5, 6, 8, 9, 10** that many forward · **Joker** any card.
- **J** swaps one of your marbles on the ring with another player's marble on the ring (not a protected one).
- **7** is split among your marbles (all 7 steps must be used); every marble passed over goes back to its kennel.
- A marble that just came out is **protected** on its start field: nobody may pass it or land on it until it moves.
- Landing exactly on a marble sends it back to its kennel (partner's and own marbles too).
- Into the **home** only forward, once the marble has left its start field, with the exact number and without
  jumping over marbles in the home (never backwards with the 4). Entering is optional – you may go round again.
- Who cannot play any card throws the cards away for this round.
- Alone: the first with all 4 marbles home wins (the others are ranked by marbles home and progress). Teams: with your
  4 home you play your partner's marbles; the team with all 8 home wins.

On the phone: tap a card, then the marble (the possible ones pulse; a choice like A 1/11/out or «into the home / on
along the ring» opens a small menu); the jack asks for the second marble; the 7 is split by tapping your marbles
(step counter, «−» per marble, then «Play»); the joker first asks which card it stands for. Moves are animated along
the track; the last move, the played card and the dealer are shown.

**Coins for places 1–3:** set by the parents in Games › Kartenlauf (default 10 / 5 / 2), paid once, only at a
family table with **at least two people of the family** – never alone against bots, to guests or to bots. With teams
both winners get place 1, the other team place 2. Every person gets a history entry.

### Stadt-Land-Fluss

Games → **🏙️ Stadt-Land-Fluss**: the classic word game live – everybody writes on their own device. Only people play
(the family and guests via QR code, no bots), at least two. Who opens the **family table** chooses (remembered):

- **3 to 8 categories**: Stadt, Land, Fluss, Tier, Name, Beruf (the default) and Pflanze, Essen, Gegenstand, Sportart,
  Schweizer Ort, Farbe, Musikinstrument, Körperteil, Spielzeug, Getränk – plus up to **2 own categories** (typed text);
- **3, 5, 8 or 10 rounds**; **time per round** 60 / 90 / 120 / 180 seconds or «until somebody calls Stopp!»;
- **«Stopp!»** on / off: who has filled every field (each answer starting with the letter) may call it – the others
  get **10 more seconds** (always on without a time limit);
- **difficult letters** C, Q, X, Y (off by default). Umlauts are never drawn, no letter comes twice in a game.

A round: the letter spins and lands, a countdown ring runs. One field per category (Enter jumps to the next field, a
✓ shows an answer that starts with the letter); answers are **saved while typing**, the server takes them until two
seconds after the end, so nothing is lost when the time runs out. «x of y finished» shows how many filled every field
– the answers of the others are never sent before the round is closed. Who leads can close the writing early.

**Checking:** an answer counts when it starts with the letter – capitals, accents and a leading article do not matter
(«die Aare» → A, «Écosse» → E, «Ägypten» → A). Empty or wrong-letter answers score 0. Then every device shows all
answers per category: tap **👎** on an answer of somebody else you find invalid – it is out when a **strict majority of
the other players** rejected it (with two players one 👎 is enough). Who leads can decide an answer with **✓ / ✗**
(this wins over the votes, also for a wrong letter). The review closes when everybody pressed «Done» or who leads goes
on. **Points per category:** the only valid answer 20, a valid answer nobody else gave 10, the same valid answer as
somebody else 5 (same text after the normalisation), invalid / empty 0. A scoreboard follows each round (with the
answers of the round); after the last round the result shows the ranking (a tie shares the place) with confetti for
the winner. Who leads can end the game any time: the rounds so far count (a round in its review is scored as it stands,
a round still being written is dropped).

**Coins for places 1–3:** set by the parents in Games › Stadt-Land-Fluss (default 10 / 5 / 2), paid once, only at
a table with **at least two people of the family** and only when at least one round was played – never to guests.
Every person of the family gets a history entry (place, points, rounds).

### Zeichnen & Raten

Games → **🎨 Zeichnen & Raten**: one draws, the others guess – live, everybody on their own device. Only people play
(the family and guests via QR code, no bots), 2 to 8 players. Who opens the **family table** chooses (remembered):

- **the words**: Animals, Jobs, Food & fruit, Things at home, Sports or **Mixed** (the default) – about 40 simple,
  drawable words each (`zeichnen_data.py`), in the language of each device (the word, the letter mask and the hints);
  a guess counts in the guesser's language and in the drawer's, so a mixed table plays together;
- **how often everybody draws**: 1, 2 or 3 times (in seat order); **time to draw** 60 / 80 / 120 seconds;
- **hints** on / off: some letters of the word appear at 50 % and 75 % of the time (at most a third of the letters).

A turn: the drawer gets **3 words** to choose from (10 seconds, then one is taken at random) and draws on a square
canvas (touch or mouse): 10 colours, 3 brush sizes, eraser, undo of the last stroke, clear. The strokes go to the
server in small batches (normalised coordinates, every ~120 ms); the others see the drawing appear live – their app
asks only for what is new (a cursor), at most 30 000 points per drawing. The guessers see the word only as a mask
(«_ _ _ _», the number of letters, the hint letters) and type guesses. A guess is right when it matches the word or an
alias – capitals, accents, umlauts (ä = ae = a), ß, der / die / das / ein …, spaces and hyphens do not matter; words of
five letters or more allow **one typo**. One or two letters off: only the guesser sees «Close!». Wrong guesses appear in
the chat for everybody – except guesses that contain the word (only the guesser sees them); a right guess is never
shown, the chat says «Mia guessed it! ✅».

**Points:** a right guess gets 50 + 50 × the part of the time left, less 10 % for each player who found it before (at
least 10) – the first and fastest gets the most; the drawer gets **10 points per player who found the word**. The turn
ends when everybody found it or the time is up; the word is shown to all for 3 seconds, then the next drawer. Who leads
can **skip** a turn (the points so far stay) and **end** the game (a drawing in progress counts as it stands). After the
last turn the result shows the ranking (a tie shares the place) with confetti for the winner and the list of words.

**Coins for places 1–3:** set by the parents in Games › Zeichnen & Raten (default 10 / 5 / 2), paid once, only at a
table with **at least two people of the family** and only when at least one turn was played and somebody scored – never to guests. Every
person of the family gets a history entry (place, points, words drawn).

### Fünf Würfel

Games → **🎲 Fünf Würfel**: the dice game with five dice and a score sheet (after the public-domain «Generala / Yacht»
family), played live – everybody rolls **at the same time** on their own device. Play **alone against 1–5 bots**
(levels easy / normal / hard, reaction time as in the other games) or open a **family table** (up to 6 players,
optionally with bots; guests via QR code). The dice are rolled on the server, the app only animates them.

A game has **13 rounds**. In every round each player rolls up to **3 times**; between the rolls tap dice to **hold**
them (they are not rolled again). Then the player fills **one free box** of their sheet – the app shows the points every
free box would give – or crosses one out with 0. When everybody has filled a box, the next round starts (meanwhile the
app shows who is still rolling). Everybody sees all sheets; nobody can touch somebody else's dice.

| Box | Points |
|---|---|
| Ones … Sixes | the sum of the dice with that number – **35 bonus** with 63 or more in this upper section |
| 3 of a kind / 4 of a kind | 3 / 4 alike: the sum of all dice |
| Full house | 3 + 2 alike (two different numbers): 25 |
| Small straight / Large straight | 4 / 5 in a row: 30 / 40 |
| Fünfling | 5 alike: 50 |
| Chance | the sum of all dice |

House rule (start dialog, on by default): **+50 for every further Fünfling** when the Fünfling box already holds 50.
The highest total wins (a tie shares the place); the result shows the ranking with confetti and every sheet. Who
leads may **end** the game early: the sheets count as they stand, but without coins.

**Coins for places 1–3:** set by the parents in Games › Fünf Würfel (default 10 / 5 / 2), paid once, only for a
game played to the end at a family table with **at least two people of the family** – never alone against bots, to
guests or to bots. Every person of the family gets a history entry (place, points).

### Heimwärts

Games → **🏠 Heimwärts**: the classic cross-and-circle race board game (public-domain mechanics of the Pachisi / Ludo
family) with its own board. Play **alone against 1–3 bots** (levels easy / normal / hard, reaction time as in the other
games) or open a **family table** (2 to 4 players, optionally with bots; guests via QR code). Everybody plays on their
own device; the die is rolled on the server, the app only animates it.

The board has a shared track of **40 fields** (10 per colour), clockwise, each colour with a yard of **4 pieces**, a
start field (★) and **4 home fields**; each player sees their own colour at the bottom. On your turn tap the die, then
tap one of the glowing pieces – only legal moves glow, the target fields are marked. With only one possible move the
piece moves by itself after a moment; with none the turn passes by itself.

- A **6** brings a piece out of the yard onto your start field (if no own piece stands there) – and **every 6 rolls again**.
- No piece out on the board (all in the yard, or the rest settled in the home)? **Three tries** to roll a 6.
- Landing on another player's piece sends it **back to its yard**; two own pieces never share a field.
- The **start fields are safe**: a piece there cannot be hit, pieces of different colours may share it.
- After a full round a piece goes into its **home** – never jumping over a piece in the home.

Rule options (start dialog, remembered):

| Option | Default | Effect |
|---|---|---|
| Benches (Eile mit Weile) | off | 4 more safe benches halfway along the arms. A piece on a start field or a bench cannot be hit, and **no other piece may pass or land there** – only the owner of a start field coming out of the yard sends a piece sitting on it back home |
| Exact number into the home | on | off: a piece goes as deep into the home as the number and the free fields allow |
| Play on for places 2 and 3 | on | off: the game ends when the winner is in, the others are ranked by how far they are |

The first with all 4 pieces home wins; with «play on» the game ends when one player is left (or only bots are left).
Bots: easy moves mostly at random, normal prefers hitting, coming out and the leading piece, hard also weighs safe
fields and the danger from pieces up to 6 fields behind. Who leads may **end** the game early: ranked as it stands,
but without coins.

**Coins for places 1–3:** set by the parents in Games › Heimwärts (default 10 / 5 / 2), paid once, only for a
game played to the end at a family table with **at least two people of the family** – never alone against bots, to
guests or to bots. Every person of the family gets a history entry (place, pieces home).

### Jump

Games → **🦘 Jump**: a live jumping race. Every player has their **own lane** – all lanes are stacked on the screen, your
own one big at the bottom with your avatar on the right, the others small above it (with their small avatars). The
obstacles come from the left; tap the **big jump button** (or your own lane, or press the space bar) to jump over them.
Play **alone** (high score: run as far as you can – your **personal best** is kept; optionally with 1–5 practice bots)
or open a **family table** (1 to 6 players, optionally with bots; guests via QR code). Everybody plays on their own device.

- **Same obstacles for everybody:** the server picks a seed, every app builds the same course from it, and all lanes
  run on the same game clock (a 3-second countdown after the start).
- **It gets faster:** the speed grows steadily (the maximum after about 2 ½ minutes); from medium speed there are also
  double crates, at high speed long hedges.
- **Crates are safe to land on:** come down on top of a crate and you stand on it and run along (you can jump on from
  there, or just walk off its end). Only running into its **side** costs a life (a little landing grace: feet a bit
  below the top still land on it).
- **Cacti** (green, with spikes and a flower) and hedges sting: touching one – also landing on it – costs a life.
- **Cloud parcours:** after about **45 seconds** (and then again about a minute after the end of the last one) a
  signpost and a blinking banner «Cloud course ahead!» announce it (about 3 seconds of free ground before it). Then
  come 4–6 crates floating on clouds (heights a little above a normal jump over a crate, never more than a small step
  up or down from one to the next), a short jump apart, over a **dense cactus field**: jump from crate to crate.
  Falling down onto the cacti costs a life (one per piece of the field, then you hop up and blink – you can jump back up
  onto the next cloud crate from the ground). After the last crate there is free ground to land on, then the normal
  course goes on. The jumps are fair for children: about half a second of good jump times for each crate.
- **Jumping:** only from the ground or a crate (no double jumps in the air); a jump just after walking off an edge
  still counts.
- **Lives:** everybody starts with 3 (start dialog: 1 / 3 / 5). Every hit costs a life, then you hop up a little and
  blink for a moment (invulnerable). Without lives you are out – the lane shows how far you came.
- **The others:** their jumps and lives show in their lanes – drawn a moment late, from the jump times their apps report.
- **The end:** at a family table the **last one still running wins** (the game ends when one is left or no person is
  left); alone you run until you are out. Places: who stayed in longest; the distance (m) is the score.
- **Bots** (easy / normal / hard) run the same physics: they look ahead for the jump times that get them past the next
  danger (over a cactus, onto a crate, onto the next cloud crate) and aim for the middle with a small timing error, and
  now and then forget to jump – the faster the game, the more they miss.

The jump physics run in the app (no waiting for the network), step by step 120 times a second – the same code in the
app and on the server (for the bots), so every app draws the others' lanes exactly from their jump times. The app
reports its jumps and hits to the server, which keeps the lives and the state per player and checks only sane values (a
time near the game clock, an obstacle that really passes then – never a cloud crate –, one life per obstacle). An app that stays silent for 12 seconds is out (left the game). Who leads
may **end** the game early: ranked as it stands (the ones still running by their lives), but without coins.

**Coins for places 1–3:** set by the parents in Games › Jump (default 10 / 5 / 2), paid once, only for a game played
to the end at a family table with **at least two people of the family** – never alone, to guests or to bots. Every
person of the family gets a history entry (place, distance, new personal best).

### Star Runner

Games → **🌠 Star Runner** (Sternschnuppen-Lauf): a live endless runner with its own little story – at night the big
lantern of the village went out; the children run as forest messengers along a forest path and catch the falling
**star sparks ✨** to light it again. The path has **three lanes**; you run with **your own avatar** (face, hair,
outfit and worn items on running legs), seen from the front, the village with its lantern on the horizon – the more
sparks you catch, the brighter it glows.

- **Controls:** swipe **left / right** to change the lane, **up** to jump, **down** to duck. On a computer the arrow
  keys or W A S D (space jumps); four buttons ◀ ▲ ▼ ▶ below the path work everywhere.
- **On the path:** fallen **logs** and **puddles** (jump), **low branches** with hanging vines (duck), **rocks** and
  **tree stumps** that block a lane (change the lane), sparks on the ground and high above some logs (jump for them).
  Every row of obstacles leaves at least one lane open; the speed grows (the maximum after about 2 minutes), the rows
  come closer together.
- **Everybody at the same time:** alone (high score, optionally with 1–7 practice bots) or at a **family table** (1 to
  8 players, optionally with bots; guests via QR code). Everybody runs the **same course** (a seed of the server) on
  their own device; the others run along as **translucent ghosts** with their avatars and name tags – the ones with
  more sparks a little ahead, a player who is out stays behind. Ghosts never collide with you. Above the path a live
  **mini ranking** (points, 💥 for who is out).
- **Lives:** 3 (start dialog: 1 / 3 / 5); a hit costs one, then you blink for a moment. **Time:** 2 / 3 / 5 minutes
  (default 3). The run ends when no person is running any more or the time is up.
- **Points:** every metre 1, every spark 10. Places by points (the same points share the place). Personal best (points)
  is kept.
- **Bots** (easy / normal / hard) play by the same rules: they plan their swipes a moment ahead with a timing error and
  now and then a mistake (forget to jump or duck, swerve too late) – the faster, the more mistakes.

**What the server decides:** the app runs the game at 60 fps by itself, but reports only its **inputs** (each swipe with
its game time). The server replays them on the course with the same rules and decides **itself** which obstacle hit
and which spark was caught – an app cannot report a distance, sparks or "no hit". An input counts only when it arrives
in time: not before the previous one, not ahead of the server's clock and not for a part of the course the server
already settled (1.5 s behind the game clock), so nobody can dodge afterwards. An app that stays silent for 10 seconds
is out. Who leads may **end** the game early: ranked as it stands, without coins.

**Coins for places 1–3:** set by the parents in Games › Star Runner (default 10 / 5 / 2), paid once, only for a game
played to the end at a family table with **at least two people of the family** – never alone, to guests or to bots.
The winner gets the «No. 1» hat. Every person of the family gets a history entry (place, points, metres, sparks, new
personal best). In the parent area › Games the runner can be active, active without bots or inactive.

### Snack Rush

Games → **🍔 Snack Rush** (German «Imbiss-Express»): a live snack-stand race. Every player runs their **own snack stand**
on their own device, all at the same time, and **all stands get the same customers**. Play **alone** (high score: your
**personal best** till is kept; optionally with 1–5 practice bots) or open a **family table** (1 to 6 players,
optionally with bots; guests via QR code).

The screen (one phone screen, no scrolling): on top the **till 💰**, your stars ⭐, angry customers 😡 and the time left;
below it a chip for every other player with **their till and their angry customers** (updated about every second);
then the **counter** with up to 4 customers (their order, their mood 😊 → 😐 → 😠 → 😡 and a patience bar; more customers
wait in the line «+2 🚶»), the **shelf** with the ready food and the **bin**, and the **kitchen** with its stations.

- **Foods and steps** (each step takes its time – a ring runs round; the stations have 2 places, the prep counter 3):
  burger = grill 4 s → assemble 2 s · hot dog = pot 3 s → into the bun 1.5 s · fries = fryer 5 s → salt 1 s ·
  drink = fill 3 s · pizza = oven 6 s · ice cream = machine 2 s. Who opens the table chooses the foods on the menu.
- **Playing:** tap an empty place of a station to start its food; tap the done food to move it on (to the prep
  counter, or onto the shelf). **Take it off in time:** grill and fryer burn it 4 s after it is done, the oven after
  5 s, the ice cream melts after 6 s – tap it into the bin. Tap a **customer** to hand over what they ordered from the
  shelf (or tap a food on the shelf: it goes to the customer who has waited longest for it). When the whole order is
  there, the customer pays.
- **Money (the game's own pretend money 💰, not the coins of the app):** every step costs its ingredients when it starts
  (burger 2 + 1, hot dog 2 + 1, fries 1, drink 1, pizza 3, ice cream 1 – half on «easy»). A served customer pays the
  prices (burger 8, hot dog 6, fries 4, drink 3, pizza 7, ice cream 4) plus a **tip** for fast service: 3 stars (more
  than 60 % patience left) +3, 2 stars +1, 1 star nothing. The till = earnings − ingredients.
- **Angry customers** walk away without paying. What was already handed to them goes back onto the shelf for the next
  customer who wants it. Food on the shelf gets **cold after 25 seconds** and goes into the bin (the money is lost –
  the app shows «🗑️ −💰…»).
- **It gets harder:** customers come more often, order more (1 → 3 foods) and are less patient – the full rush after
  about 4 minutes. Level easy / normal / hard: how often customers come and how patient they are.
- **Duration:** 3, 5 (default) or 8 minutes – the **most money in the till wins** (then more served customers, more
  stars, fewer angry ones; the same shares the place). Optional «Out after angry customers» (off by default, or 3 / 5 /
  8): with that many angry customers you are out (your till stays); the game ends early when no person is left in.
- **Bots** (easy / normal / hard, the level of the table) work through the customers in order: a reaction time, some
  seconds of work per food, sometimes they forget a part (costs time and ingredients) and they let hopeless customers
  go – so they fall behind when it gets busy.

The kitchen runs in the app (no waiting for the network). The server makes the customer stream from a secret seed (the
apps only get the customers of the next seconds), and the app reports its serves, the customers it saw leave angry and
the money spent. The server checks every serve: each customer only once, not before they came, not after their patience
ran out, not in the future – and the stand must have been able to make the food: every serve books its foods step by
step on the earliest free place of each station (food made ahead at most 90 seconds before), the last step must be done
by the serve. A customer without a valid serve is angry – the server decides that itself 4 seconds after the patience
ran out. The money spent counts at least the ingredients of every served food. When «Out» is on, an app that stays silent
for 20 seconds is out. Who leads may **end** the game early: ranked as it stands, but without coins.

**Coins for places 1–3:** set by the parents in Games › Snack Rush (default 10 / 5 / 2), paid once, only for a game
played to the end at a family table with **at least two people of the family** – never alone, to guests or to bots. The
winners get the «No. 1» hat. Every person of the family gets a history entry (place, till, served customers, new
personal best). In Games the parents can switch the game on, off or to «active without bots».

### Traffic Cadet (Verkehrskadett)

Games › **🚦 Traffic Cadet**: a live traffic game. Every player regulates the traffic lights of **their own map** on
their own device – all maps get the **same streets and the same cars** (from the server). Alone (optionally with
practice bots), at the family table (1–6 players, bots fill up, guests via QR code).

- **Switching:** tap a traffic light on the map (or its big button below the map) – it switches its whole group (e.g.
  «1 ↓↑» = north and south together): green → **amber** (1.5 s) → red, red → green at once. At the start of every
  world all lights are red.
- **The cars:** cars, buses (slower, longer), bikes (slow) and now and then an ambulance 🚑. They stop at red (and at
  amber when they still can), go at green, keep their gap and turn as their route says. Cars queue outside the map when
  there is no room («+3» at the edge).
- **Accidents 💥:** two cars of crossing or merging routes in the junction at the same time crash; both block the way
  for 4 seconds (the others wait), then they are towed away. So: switch one direction red, wait until the crossing is
  empty, then the other green.
- **Moods:** waiting makes drivers annoyed (😐 → 😠) and then angry 😡 (difficulty normal: after 10 / 20 seconds of
  waiting; easy 12 / 24, hard 7 / 14). The ambulance is in a hurry: angry after 6 seconds. Angry drivers honk.
- **Out:** too many accidents or angry drivers, counted over all worlds – easy 5 / 15, normal 3 / 10, hard 3 / 8. Who
  is out watches the others' live stats.
- **Worlds** (start dialog: 1–5), each 5 s intro («World 2: T-junction») + 90 s of traffic, the traffic grows during a
  world: 1 **simple crossing** (only straight on, 2 groups) → 2 **T-junction** with a left-turn lane (3 groups) →
  3 **crossing with turning lanes** (straight/right and left separately, 4 groups) → 4 **two connected crossings** (the
  road between them can fill up and block the crossing behind) → 5 **roundabout** (the drivers yield to the ring by
  themselves; you have a stop/go light at every entry to give the others a gap). Everybody still in moves on together.
- **Difficulty** (easy / normal / hard): how many cars come, how patient the drivers are, how many accidents / angry
  drivers put you out.
- **Live bar:** at the top every other player's accidents 💥, annoyed 😠 and angry 😡 drivers and cars through 🚗
  (updated about every second), below my own stats, the world and the time left in it.
- **Points:** every car through 1 (bus 2, ambulance 3), minus 5 per accident and 2 per angry driver. **Places:** who is
  still in after the last world by points; who is out after them (who lasted longer first). At a family table the
  game ends when only **one is left standing**. Alone your best points are kept.
- **Bots** (easy / normal / hard) run the same simulation on the server: they give green to the set of groups with the
  most waiting cars, switch with a clearance pause (amber, then until the crossing is empty) – easier bots forget the
  pause more often (crash risk) and leave a direction green too long.

The map is simulated in the app (10 steps per second, integer arithmetic only) from the server's world (layout + the
stream of cars from the game's seed) and the player's switches; the app reports only its switches (with their tick).
The server runs **the same simulation** about 1.5 s behind (identical in Python and JavaScript – tested) and its result
counts: accidents, angry drivers, cars through, out. A switch for a moment the server simulated already is refused and
the app rebuilds its map from the server's snapshot. An app silent for 15 seconds is out. Who leads may **end** the
game early: ranked as it stands, no coins. Parents › Games: active, active without bots (no practice bots, no bots at
the table) or inactive.

**Coins for places 1–3:** set by the parents in Games › Traffic Cadet (default 10 / 5 / 2), paid once, only for a game
played to the end at a family table with **at least two people of the family** – never alone, to guests or to bots;
the winner gets the «No. 1» hat. Every person of the family gets a history entry (place, points, cars, accidents, angry
drivers).

### 24h Endurance (24-Stunden-Rennen)

Games › For a game night › **🏎️ 24h Endurance**: a **short, fast team race** on the fictional **Circuit des Tannes**.
Every team is a racing stable with **one car**; the family splits into 1–4 teams at the table (1–5 people per team,
guests via QR code join a team too), **bot teams** race along. Alone you race against bot teams. A family table needs
at least two cars (without bots: two teams of people).

- **Team look in the lobby:** every team chooses its **colour** (palette of 8, each colour once), its **country** (66
  countries in four groups – Europe, Americas, Asia & Middle East, Africa & Oceania – alphabetical in the viewer's
  language, or «no country»; the suggestion is the family's own country from the app's language, e.g. de-CH → 🇨🇭) and
  its **car number** (1–99, each number once). The flag is shown on the car, in the standings and on the podium (emoji
  flags; where the device has none, e.g. Windows, the country code as a small chip).
- **24 race hours in 5 / 8 / 12 minutes** (default 8). The race clock starts at 15:00 and runs through **dusk, night
  (headlights, a shorter view) and dawn** into the next afternoon. **Rain showers** (on by default): sudden showers of
  30–55 s every 1–2 minutes; everybody sees the forecast («Rain in ~20 s»). **Winner: the most laps** (then distance, then who reached the line first).
- **Intro:** the drivers run to their cars, doors close, engines roar, five red lights → **GO!** (about 6 s).
- **One short lap (about 20–30 s), then the car drives into the pits by itself – after every lap.** At every stop the
  **driver changes**: the next person of the team drives (in turn), the driver joins the crew. Two people take turns;
  alone (or when the whole crew is offline) the **garage** prepares: every stop takes a fixed **5 s** (+4 s after an
  overheat), tyres by the forecast – and the garage plugs the spare battery in only **8 s after the stop** (fair, not
  perfect: the spare is usually 80–100 % at the next stop).
- **Driver:** three lanes – swipe or ◀ ▶ (←/→) to dodge oil, cones and slow cars; **hold 🚀 Gas** (↑ / Space) for full
  speed, **🛑 Brake** (↓) to brake, neither = lifted off. Full throttle heats the engine; in the **red it overheats**:
  the car limps to the pits and the engine is swapped there (no retirement). **Two chicanes** per lap: **braking zones**
  with boards at 150 / 100 / 50 m – too fast into a chicane (by day and dry over 23, in the rain or at night over 18
  «m/s») and the car goes **off into the gravel** (3 s very slow); then change the lane past the **kerbs** (touching one
  slows a little; in the rain or at night the kerbs reach the middle lane). Juniors – and everybody in the first two
  laps – get a big «🛑 Brake!» hint. **Slicks in the rain** and **rain tyres in the dry** are slower (and slicks slide).
  Other cars never block you: a car close to yours in your lane is drawn moving over to a free lane while overtaking.
- **Electric car – the battery 🔋:** the battery (0–100 %) drains by the metre, **much faster at full throttle** (0.16 %
  per metre – flat out a full battery does *not* last a lap) **than lifted** (0.07 % per metre – a lifted lap needs
  about 45 %); braking gives a little back. The driver sees 🔋 % in green / orange / red and **«Save energy!»** when the
  charge won't last the rest of the lap at a normal mix of full throttle and lifting (blinking big while pressing the
  gas). **Empty → «⚠️ Emergency drive mode»:** the car crawls (about 50 km/h) to the pits with its hazard lights on –
  no retirement, but it costs a lot of time.
- **Exactly two batteries per team:** the one in the car and **one spare**. At **every stop they are swapped** (part of
  the stop, a fixed 1 s): the spare goes into the car **with whatever charge it has**, the used one comes out and has to
  be charged during the next lap. It only charges while it is **plugged in**: 4 % per second (empty → full in 25 s,
  about a lap) from the moment the crew plugged it in – computed on the server from its own timestamps (plug-in time,
  swap time), never from a number the app sends. Plugged in late (other jobs first) → not full at the next stop → the
  next driver has to drive slower. The driver's screen shows «spare 🔋 63 % ⚡» rising.
- **Pit crew** (everybody else of the team) – during the lap on their phones: **🔌 charge the spare battery** (tap
  «Plug in» – first!; the charge rises on every crew phone, a cable animates while it charges), **🛞 lay out 4 tyres**
  (choose ☀️ slicks or 🌧️ rain tyres, tap the 4 spots) and, only after an overheat, **🔧 prepare the spare engine**
  (hold 2 s). Each finished job shows ✓ (also for the driver). A bar shows when the car comes in.
- **The stop** – a big stopwatch, the car in its pit box, the battery swap (the used one goes to the charger), the crew
  at work and cheering stands for the whole team: **2 s** (stop and driver change) **+ 1 s battery swap, +4 s for tyres
  not ready, engine swap +6 s (+2 s if prepared)**. A job only counts if it was finished before the car arrived. A
  super fast stop (≤ 4 s) gets a cheer. The next driver sees the charge of the battery going in («🔋 63 % – Save
  energy!»).
- Trackside banners now and then (own, invented: Family Quest, Home Assistant with an own house icon, «Snowman Tyres»).
- Now and then **fans camp beside the track** (tents, a camper van, a campfire at night) waving a sign «I ❤️ #7 🇨🇭» –
  mostly with the viewer's own car number and flag, sometimes for another team.
- **Difficulty:** junior (fewer things on the track, the engine heats slower, the braking hint always) or normal.
  **Bots** (easy / normal / hard) dodge, manage the temperature and the battery (they lift off when it would not last
  the lap), brake for the chicanes, plug their spare in first and prepare their stops (easier bots miss more jobs, plug
  in late or pick the wrong tyres). A driver whose app is silent for 6 s gets the **autopilot**.

The server simulates every car in steps of 0.1 s, 0.8 s behind the clock – the same step function runs in the app for a
smooth picture of the own car (tested to give the same numbers). The driver's app only reports its inputs (lane, gas /
brake); the crew's jobs are actions timed by the server (plug in, a tyre on a spot, start / stop holding). Who leads may end the
race early: ranked as it stands, no coins. Parents › Games › 24h Endurance: the defaults (race length, weather,
difficulty, people per team), active / without bots / inactive, the coins.

**Coins for places 1–3:** default 10 / 5 / 2 for every person of the family in that team, paid once, only for a race
run to the end at a family table with **at least two people of the family** – not alone, not for guests or bots; the
winning team gets the «No. 1» hat. Records: **most laps** and the **fastest pit stop** per person (garage stops do not
count; also questions in «Family Quest Facts»). Every person of the family gets a history entry (place, laps, team,
best pit stop, drives, stops).

### Klatsch den Beat

Games → **👏 Klatsch den Beat**: a live rhythm game – **everybody plays at the same time**, each on their own device.
Every round the app plays a short beat with its own drum sounds (kick, clap, hi-hat – made in the browser, no sound
files), then everybody **claps it back** on the big clap button. Play **alone** (personal best; optionally with 1–7
practice bots) or open a **family table** (1 to 8 players, optionally with bots; guests via QR code). Turn the sound on!

- **A round** (call and response): a **count-in** of four clicks, then **listen** – the pattern sounds over the groove and
  its dots light up on a bar of 16 steps; then a **run-up** of four clicks («get ready»); then the **clap bar** – the same dots stay, a playhead sweeps over them, clap
  when it reaches a dot. A short pause shows your points and the live ranking, then the next round starts by itself.
  We chose this variant over notes sliding to a hit line: you hear the beat first (the fun part of clapping along) and
  the dots still help children who cannot remember the whole pattern.
- **It gets harder:** the tempo rises from 80 to 140 BPM over the rounds (5–8, start dialog); first quarters and eighths
  on the «one», then syncopes (off-beat eighths, a missing «one»), at the end sixteenth syncopes and pauses. Notes are
  always at least an eighth apart. The server makes the patterns (random), everybody gets the same ones.
- **Points:** every note takes the nearest clap – within **±60 ms perfect** (100 points), within **±130 ms good** (50),
  else missed; a clap that hits no note costs 25 points (no drumming through), never below 0 per round. Most points
  win; the same total shares the place. The result also shows the accuracy (perfect = 1, good = ½ of a note).
- **Fair timing:** every app knows the server clock (it estimates the offset from the server's answers, the one with
  the shortest round trip counts), plans the sounds on the audio clock and reports its claps as game times; the server
  judges them a second after each clap bar for everybody at once. Phones and Bluetooth headphones play sounds late:
  **calibrate** once (🎚️ – tap along to 8 clicks); the delay is kept on this device and subtracted from your claps.
  A tap vibrates the phone where the browser supports it; the space bar claps too.
- **Bots** (easy / normal / hard) clap every note with a timing error and now and then miss one or clap once too much.

Who leads may **end** the game early: the rounds already played count, ranked as it stands, but without coins. The
accuracy of a game played to the end is your **personal best** (alone or at a table).

**Coins for places 1–3:** set by the parents in Games › Klatsch den Beat (default 10 / 5 / 2), paid once, only for a
game played to the end at a family table with **at least two people of the family** – never alone, to guests or to
bots. The winners get the «No. 1» hat; every person of the family gets a history entry (place, points, accuracy).

### Verbotene Wörter

Games → **🚫 Verbotene Wörter**: the explaining game – one explains a word **without saying the forbidden words**, the
others guess aloud. Everybody has the app on their own device; the talking happens at the table. Only people play (the
family and guests via QR code, no bots), 2 to 8 players. Who opens the **family table** chooses (remembered):

- **the cards**: Easy (younger children), Normal or Mixed – about 370 built-in cards, each with a word and
  5 forbidden words (`verboten_cards.json`), shown in the language of each device – the forbidden words are the obvious
  ones of that language;
- **time per turn**: 30 / 45 / 60 / 90 / 120 seconds (default 60); **how often everybody explains**: 1–4 times;
- **«Skip» costs** nothing or 1 point; **two teams with 4 or more players** on / off.

**Teams** (4 or more players, on by default): every second seat is in team A, the others in team B (who leads can mix
the seats in the lobby). The teams take turns, the members of a team explain in turn (a smaller team's members explain
a little more often, so both teams get the same number of turns). With 2 or 3 players – or teams off – **everybody
plays for themselves**.

A turn: the explainer taps **Go!** and the clock runs (kept by the server). Only the explainer sees the card – with
teams also the **other team** (the classic rule: they watch for forbidden words); the explainer's own team never gets
the card on their device, they see the clock, the score and how many cards are done. The explainer taps:

| Button | Points |
|---|---|
| ✅ Got it | +1 for the team – alone: +1 for who guessed it (the explainer taps the name) **and** +1 for the explainer |
| 🚫 Forbidden word | −1 for the explainer's team (alone: the explainer) |
| ⏭ Skip | 0 or −1 (start dialog) |
| 🔔 Buzz (the other team) | −1, like «Forbidden word» |

Then the next card comes. Every tap names its card, so a buzz and a tap at the same moment count only once. When the
time is up, the card on the table does not count; everybody sees the cards of the turn and the next explainer gets
ready. Who leads can **skip** a turn (e.g. the explainer left) and **end** the game (a turn in progress counts as it
stands). The result shows the ranking (a team shares its place, a tie shares the place), confetti for the winners and
every card of the game.

**Coins for places 1–3:** set by the parents in Games › Verbotene Wörter (default 10 / 5 / 2), paid once, only at
a table with **at least two people of the family** and only when at least one turn was played and somebody scored –
never to guests. Every person of the family gets a history entry (place, points, team, cards explained); the winners
get the «No. 1» hat.

### Jass

Games → **♣️ Jass**: the Swiss card game **Schieber** (traditional rules). **4 players in 2 teams** – partners sit
opposite. Play **with 3 bots** (levels easy / normal / hard, reaction time as in the other games) or open a **family
table**: any mix of the family, guests (QR code) and bots – free seats are taken by bots (alone with 3 bots, 2 children
with 2 bots, …). With two people and two bots the people play together as partners (start dialog; off: against each
other); who leads can **mix the seats** in the lobby. Everybody plays on their own device, the server deals (with
`secrets`) and checks every card – the app only shows your own cards.

The screen: your hand fanned at the bottom (only the cards you may play light up – tap one to play it), your partner on
top, the opponents left and right with their number of cards, the trick in the middle, the trump and the score of both
teams on top (with the points of the running round). 🕘 shows the last trick, 📋 the score sheet (every round).

- **Cards**: Swiss (Schellen, Schilten, Rosen, Eicheln; 6–9, Banner, Under, Ober, König, Ass) or French (♠ ♥ ♦ ♣;
  6–10, J, Q, K, A – the J counts as Under, the Q as Ober). 36 cards, 9 each.
- **Choosing the game**: who is on turn chooses **Trumpf** (one of the 4 suits), **Obenabe** (no trump, the Ass is
  highest) or **Undeufe** (no trump, the 6 is highest) – or **pushes** («schieben») to the partner, who must then
  choose. In the first round the holder of the Schellen 7 (♦ 7) chooses, then the next player to the right. The player
  who chose (or pushed) leads the first trick; the winner of a trick leads the next one.
- **Following**: follow suit if you can; you may always **trump in** instead – but never **under-trump** (play a trump
  lower than one already in the trick) unless you only hold trumps. Trump led: you must follow with trump – except when
  the **Buur** is your only trump (he may always be held back).
- **Ranking**: trump Buur (Under / J) > Nell (9) > Ass > König > Ober > 10 > 8 > 7 > 6; other suits and Obenabe
  Ass > König > Ober > Under > 10 > 9 > 8 > 7 > 6; Undeufe the other way round.
- **Points**: trump Buur 20, Nell 14, Ass 11, König 4, Ober 3, 10 10; other suits Ass 11, König 4, Ober 3, Under 2,
  10 10; Obenabe and Undeufe: the 8 counts 8 (Undeufe: the 6 counts 11, the Ass 0). The last trick **+5** – always
  157 per round; all 9 tricks to one team (**Match**) **+100**.

Rule options (start dialog, remembered):

| Option | Default | Effect |
|---|---|---|
| Cards | Swiss | Swiss or French cards (the card backs as in Tschau Sepp) |
| Game to | 1000 points | 500 / 1000 / 1500 / 2500 points (checked at the end of a round – both teams over it: more points wins) or 1 / 2 / 4 / 8 / 12 rounds |
| Weis | on | declared with the first card (automatically): 3 in a row 20, 4 in a row 50, 5 in a row 100, 6 / 7 / 8 / 9 in a row 150 / 200 / 250 / 300; 4 Under 200, 4 Nell 150, 4 Ass / König / Ober / 10 100. Only the team with the **best single Weis** (more points, then more cards, then the higher card – Undeufe the lower –, then trump, then who played first) writes **all** of its Weis; the cards are shown after the first trick |
| Stöck | on | König and Ober of trump in one hand: 20 points, announced with the second of them, always counted |
| Multipliers | off | Rosen / Schellen (♥ ♦) ×1, Schilten / Eicheln (♠ ♣) ×2, Obenabe / Undeufe ×3 – the whole round counts that many times |
| Partners | on | two people with two bots play together |

After a round the result stays on the table for a moment (cards, Match, Weis, Stöck) – **Next round** deals at once.
Bots: easy plays mostly at random, normal follows simple rules (take a trick with points, give points to the partner),
hard counts the cards, pulls trumps, gives points («schmieren») when the partner's card is safe, chooses the trump by
the strength of its hand and pushes a weak hand. Who leads may **end** the game early: ranked as it stands, but without
coins.

**Coins:** the members of the **winning team** get the coins for place 1 (set by the parents in Games › Jass,
default 10), paid once, only for a game played to the end at a family table with **at least two people of the family**
– never alone against bots, to guests or to bots. Every person of the family gets a history entry (won / lost, the
points, the partner); the winners get the «No. 1» hat (not on a tie).

### Werwölfe

Games → **🐺 Werwölfe**: the classic social deduction party game, played in **one room** – the app is the game
master. Everybody has the app on their own phone (the family and guests via QR code), **2 to 12 people** – a game
has 5 to 12 players: with **fewer than 5 at the table, bots fill it up to 5** when who leads begins (the animal bots
of the card games, with their emoji). Who opens the **family table** chooses (remembered; also changeable in the lobby
once everybody is there):

- **the roles**: *by the number of players* (recommended) – 5: 1 werewolf + seer · 6: + witch · 7: 2 werewolves ·
  8: + hunter · 9–10: + Amor · 11–12: 3 werewolves – or by hand: 1–3 werewolves and seer / witch / hunter / Amor on or
  off (fewer werewolves than half of the players); everybody else is a villager;
- **time to talk by day**: 1, 2, 3 (default), 5 or 10 minutes;
- **fill with bots up to**: 5 (default) to 12 players – more bots for a bigger game (no bots when enough people are
  there).

**Bots** play every role and act by themselves after a short «thinking» time (at night 4–10 seconds, so the length of
a step does not give away who holds the role; in the vote one after the other): Amor links two random players, a bot
werewolf bites the choice of a human werewolf (else a random non-werewolf – the bot werewolves always agree), the
seer looks at a random player, the witch heals the victim about every second time and rarely poisons somebody, the
hunter shoots a random player; in the vote a bot werewolf votes for a non-werewolf, the other bots for a random
player – a bot seer votes for a werewolf she saw, and while she lives the other village bots lean the same way. A
bot's role stays as secret as a person's. The talk timer runs as before; who leads still lets the night fall and
opens the vote.

| Role | Power |
|---|---|
| 🐺 Werewolf | at night chooses a victim together with the other werewolves (they know each other) |
| 🧑‍🌾 Villager | none – talk, listen, vote |
| 🔮 Seer | every night sees the role of one living player (only she sees it) |
| 🧪 Witch | sees the werewolves' victim; one healing potion and one poison potion for the whole game (both in one night is allowed, she may heal herself) |
| 🏹 Hunter | when he dies (night or vote) he shoots one living player |
| 💘 Amor | in the first night links two players (himself allowed) as lovers: when one dies, the other dies of grief |

**The game:** everybody looks at their secret role (tap the card to reveal, tap again to hide – the 🎭 button shows
it again later). Who leads lets the **night** fall: all phones show a dark «eyes closed» screen, only the active role
gets its buttons, in this order: **Amor** (first night) → **werewolves** → **seer** → **witch** (a role that is dead
is not called). The werewolves see each other's choice; when **all living werewolves agree**, the victim is chosen.
If who leads moves on, the target with the most werewolf votes counts – a tie: nobody dies. **Day:** the village
learns who died and their role (not how – poison and werewolves look the same), then the talk timer runs (who leads
may skip it). **Vote** on every phone (or abstain; a vote can be changed until everybody voted): the player with the
**most votes is out** and their role is shown – a **tie (or no vote): nobody is out**. A dying hunter shoots first.

**Win:** the **village** when all werewolves are dead (everybody who is not a werewolf wins, dead or alive); the
**werewolves** when at least as many werewolves as others are alive; the **lovers** – a werewolf and a non-werewolf –
when they are the last two alive (only the two win). **Dead players** are spectators: they see every role and the
werewolves' choice and cannot act. **Secrecy:** every phone gets from the server only what this player may know –
the own role, fellow werewolves (for werewolves), the lover (for the lovers and Amor), the seer's results (seer),
the victim and the potions (witch).

**The narrator:** the phone of who leads (who opened the table, or a parent) shows the narration in big text and
plays a sound at every step; it also reads it aloud with the voice of the device (🔊 / 🔇 in the leader bar). Who
leads can **move on** when somebody is idle (every step has a default: no lovers, the most werewolf votes, no look,
no potion, no shot, close the vote) and **end** the game (no winner, no coins).

**Coins:** set by the parents in Games › Werwölfe (the amount of place 1, default 10): every person of the
family on the **winning side** – only at a table with **at least two people of the family**, only for a game played
to the end, paid once, never to guests or bots. The winners get the «No. 1» hat; every person of the family gets a
history entry (won or lost, the role) – bots none.

### Schach (chess)

Games → **♟️ Chess**: chess with the full standard rules. The card lists **your games** (running and paused – tap
one to continue), the **invitations** to you and the open seats, and three ways to start:

- **🤖 Against the bot** – easy (mostly random moves, captures preferred), normal (looks two half-moves ahead:
  material and mobility) or hard (thinks 3–4 half-moves deep with piece-square tables; answers within about 2 s).
  Choose your colour (white, black or random).
- **👥 Against the family** – invite one person of the family (the invitation shows up on their start page and in
  their chess card; they join or decline) or leave the seat **open for anybody** of the family – guests join via QR
  code (👥 Invite guests). The game starts when the second player joins; each plays on their own device.
- **📱 Two on one device** – pass and play: the board turns to whoever is to move.

**Clock** (optional): 5, 10 or 15 minutes per side, no increment. Who runs out of time loses – a draw if the other
side has nothing left to mate with.

**Playing:** tap a piece, then one of the marked squares (dots; a ring for a capture). The last move is highlighted,
a king in check glows red, captured pieces and the material lead show next to each player, the move list (in
standard notation) folds out under the board. A pawn on the last rank asks which piece it becomes. The server
checks every move: check, castling (not out of, through or into check), en passant, promotion.

**The end:** checkmate, stalemate, the same position for the third time (automatic draw), 50 moves without a capture
or a pawn move (automatic draw), not enough material to mate (K–K, K+B–K, K+N–K, bishops all on one colour),
resignation (🏳), a draw by agreement (½: the other player accepts or declines; the bot accepts only when it stands
clearly worse; on one device the draw is agreed at once), or time.

**Pausing:** either player taps **⏸ Pause** – the clock stops, nobody can move, the game waits in the database
(also over a restart) until a player taps **▶ Continue**. Several games per person at a time (up to 12 unfinished).
A game alone (bot or one device) with a clock pauses by itself when you leave it. Who started a game or a parent
can **delete** a paused game (🗑) or an open invitation. The parent area lists every chess game (Games › Chess)
and **Running games** lists them too (paused ones marked ⏸) – «End» there ends a game without a result, no coins.

**Coins:** set by the parents in Games › Chess (three numbers, default 10 / 5 / 2): the winner of a game
between **two people of the family** / a win against the **hard bot** / against the **normal bot**. Only the winner,
only after at least **10 own moves**, paid once – never against the easy bot, never on one device, never against
guests. The winner of a game between two people of the family gets the «No. 1» hat; everybody of the family who
played gets a history entry (won / lost / draw, against whom, how it ended).

### Dorfmarkt

Games → **🏘️ Dorfmarkt**: a property-trading board game in a Swiss village – generic mechanics of the genre with its
own board, names, cards and look. Play **alone against 1–5 bots** (levels easy / normal / hard, reaction time as in the
other games) or open a **family table** (2 to 6 players, optionally with bots; guests via QR code). Everybody plays on
their own device; the server rolls the two dice and checks every rule. Money is counted in **Taler** – the game's own
play money, not the coins of the app.

**The board** is a square ring of 36 fields: the corners **Markttag** (start – passing or landing brings 200 Taler),
**Gemeindehaus** (just visiting, or sitting in the «Gemeindeversammlung»), **Dorfplatz** (a free rest) and «Ab in die
Gemeindeversammlung»; 20 village shops and places in **8 colour groups** of 2–3 (from the farm shop and the bee house
up to the chocolate workshop and the watchmaker), **4 village bus stops**, 2 works (Wasserwerk, Elektrizitätswerk),
2 **Zufall** and 2 **Dorfkasse** card fields with own, kid-friendly cards, and 2 fees (Gemeindesteuer 100,
Vereinsbeitrag 75). Tap a field for its card (price, rents, owner); 🔎 zooms into the board (scrolling only inside the
board).

- On your turn tap the dice. A **double** rolls again; the third double in a row goes straight to the meeting.
- A free field: **buy** it at its price, or leave it (option **auction**: then everybody may bid once – sealed, 30
  seconds, the highest bid wins).
- A field of another player: pay the **rent** – double for an unbuilt field when the owner has the whole colour
  group. **village bus**: 25 / 50 / 100 / 200 for 1–4 stops of the owner; **works**: 4 × the dice (10 × with both).
- With a whole colour group (no mortgage in it) build **Marktstände** (1–4, evenly across the group) and then a
  **Markthalle**; buildings sell back for half. Option **mortgages** (on): a field without buildings in its group
  gives half its price, no rent while mortgaged; paying back costs 10 % more.
- **Gemeindeversammlung**: pay 50 Taler, use a free pass card, or try to roll a double (3 tries; after the third:
  pay and go).
- **Trading**: offer own fields (without buildings in their group) and Taler for fields and Taler of another
  player; they accept or decline (bots decide by the value, harder bots are stricter).
- **Debts**: who cannot pay raises the money (sell, mortgage, «sell automatically») – or is **bankrupt**: everything
  goes to the creditor (to the bank: the fields are free again).

**Game length** (start dialog, remembered): **30 rounds** by default (10 / 20 / 30 / 50), or a time limit (30 / 45 /
60 / 90 minutes), or classic until one is left – with rounds or time the **richest** wins (Taler + fields at their
price, mortgaged at half + buildings). The game is always over when only one player (or no person) is left. Taler at
the start: 1000 / 1500 / 2000. Who leads may **pause** the game (nothing moves, the time stops) and **end** it early
(ranked as it stands, without coins). The whole game is stored in the database and survives a restart of the add-on.

**Coins for places 1–3:** set by the parents in Games › Dorfmarkt (default 10 / 5 / 2), paid once, only for a
game played to the end at a family table with **at least two people of the family** – never alone against bots, to
guests or to bots. The winners get the «No. 1» hat; every person of the family gets a history entry (place, worth).

### Escape Room

Games → **🗝️ Escape Room**: the live riddle game for the family – solve the riddles of every room to find the door
code and get out. Everybody plays on their own device (the family and guests via QR code, **no bots**). Every room is
a world of its own with its own look (the wizard's tower, the pirate cabin, the space station, the treehouse, the clock
workshop, the ice castle, the jungle temple, the dragon's cave): its **objects hide riddles** – tap one to open its
riddle – and a little animal has a tip. Who opens the **family table** chooses (remembered):

- **rooms**: 1 to 5;
- **difficulty**: easy (2 riddles per room), medium, hard (3 riddles per room) or **mixed** – the rooms get harder one
  after the other (2 or 3 riddles);
- **kinds of riddles** (several): logic & codes, words & letters, pictures & observation, patterns & sequences, maths,
  memory, maps & directions, mechanical puzzles, knowledge – with the number of riddles not played yet per kind;
- **play**: all together (one team, everybody sees the same room and may try) or **two teams** (every second seat;
  who leads can mix the seats in the lobby);
- **time limit**: none, 15, 30 or 45 minutes.

**The combined lock:** every solved riddle reveals a part of the door code, shown to the whole team – a digit with a
symbol (⭐ 3), a number, or a coloured gem with its position (🔴 #2). The door needs all parts together: the digits in
the order of the symbols shown on the door, the sum of all numbers, or the gems in the order of their positions. Then
the next room opens; after the last door the team is out.

**Hints and time:** up to 3 hints per riddle (the whole team sees them); a hint costs **60 seconds**, a wrong answer
(also at the door) **10 seconds**. The team's time is the real time plus these seconds. Memory riddles show their
picture only for a moment after «Peek» (as often as you like). Mechanical puzzles (rune lamps, sliding tiles, turning
rings, water pipes, lever board) are played on the device; the moves go to the server, which checks them.

**Two teams** play the same rooms with the same riddles, each with its own progress; you see the other team only as a
progress bar. The first team out wins – counting its hint and error seconds: the game ends as soon as the other team
cannot be faster any more. With a time limit the game ends when the time is up (then nobody escaped). Who leads (or a
parent, also in Games › running games) can end the game – then nobody escapes.

**The riddles** are made new for every game by the server (random numbers, words, pictures) – the app never gets a
solution, the server checks every answer. 56 riddle kinds (level in brackets: e easy, m medium, h hard):

| Kind | Riddles |
|---|---|
| Logic & codes | The clue lock (m h) · Number detective (e m) · Three chests (m h) · The animal bench (m h) · The big scales (e m h) · The number square (m h) |
| Words & letters | Mixed-up letters (e m h) · Secret writing (m h) · Rune alphabet (m h) · The worn-out sign (e m) · Mirror writing (e) · Hidden animal (m h) · Letters as numbers (m h) · The vowel thief (h) |
| Pictures & observation | Count carefully (e m) · The odd one (e m) · Two pictures (m h) · The stopped clock (e m) · The book shelf (e m) · Coloured candles (m) · The magic mirror (m h) |
| Patterns & sequences | Number row (e m h) · The bead necklace (e m) · The tile floor (m h) · Growing towers (e m) · Letter row (m h) · The cuckoo clock (m h) · Turning arrows (e m) |
| Maths | Fruit sums (e m h) · The coin purse (e m) · The magic square (m h) · Story sums (e m) · Number pyramid (m h) · The dice tower (e m) · The number machine (m h) |
| Memory | Glowing crystals (e m h) · The magic tray (m h) · Where was it? (e m) · Flashing numbers (m h) · Past the window (e m) |
| Maps & directions | The treasure map (e m) · The compass (e m) · Bridges and paths (m h) · The robot program (m h) |
| Mechanical puzzles | Rune lamps (e m h) · Sliding tiles (m h) · Turning rings (m h) · Water pipes (m h) · The lever board (e m) · Gear chain (e m h) |
| Knowledge | Counting legs (e m) · Mixing paint (e m) · The planets (e m) · Eggs or not? (e m) · The calendar (e m) · Corners (e m) |

The **word riddles** use 45 words in all 9 languages of the app (and English): every device shows the riddle in its
own language, the answer counts in any of them (without accents).

**Already played:** the family keeps a counter per riddle kind (setting `escape_played`). A new game takes the kinds
played least – the fresh ones first – so every kind comes once before one comes again; the **round** (shown in the
start dialog and in Games › Escape Room, e.g. «32 of 56 riddles not played yet – round 2») is the lowest counter + 1.
With few chosen kinds (e.g. only memory, 5 rooms) a kind can come twice in one game – with other numbers.

**Coins:** set by the parents in Games › Escape Room (default 10): every person of the family in the team that escaped
and won gets them (together: everybody, when out; two teams: the winning team) – only at a table with **at least two
people of the family**, never to guests, paid once. Every person of the family gets a history entry (out or not, rooms,
time, hints, team); the winners get the «No. 1» hat.

### Beat the Bureaucracy

*Only in the app «Family Quest Dev» for now – it is being reworked before it comes to the beta.*

Games → **🏛️ Beat the Bureaucracy** (de «Besiege die Bürokratie», de-CH «Bsieg d Bürokratie», fr «Vaincre la
bureaucratie» …): a light-hearted family party game in the wonderfully complicated town hall of an invented town
(«Little Red-Tapington» – every language has its own funny name, e.g. «Bürokratingen», «Paperasse-sur-Tampon»). An own
parody with own texts: no real country, authority, law, person or brand. 2 to 4 teams – one device per team (one or
more people around it), the family on their own devices, guests via QR code, bots (easy / normal / hard) – or a child
alone against bot teams. About 20–30 minutes, from about 7 years.

**Goal:** every team wants its building project approved (it picks one of 8 – tree house with a rope ladder, garage
with a water slide, pizza oven in the garden, hamster palace, a pond for exactly one duck, lemonade stand with a
drive-through, igloo with a doorbell, garden shed shaped like a rocket – or they are drawn at random). The permit
needs 5, 7 or 9 stamps (game length short / normal / long); the first team with all stamps wins, the others are
ranked by their stamps.

**The town hall** (a cross-section on the screen, with a display board «Now serving 047 → Counter 2» that goes
«ding-dong»): Counter 1 «General information» (knows nothing, kindly refers you on), 2 «Office for Building Matters»
(open only on Tuesdays and at new moon – one round is one day of a Monday–Friday week, the moon goes round in 8
rounds), 3 «Office for Green Spaces» (asks whether the tree agrees), 4 «Commission for Slowness» (meets every 3
rounds; in between your application goes on the pile and is decided at the next meeting – 70 % approved), the
archive in the basement (fetches the missing document – sometimes first the form you need for the form) and the
coffee kitchen (a trick card, a rumour and better relations). The clerks chat with each other in speech bubbles
(weekend plans, the coffee machine, the plastic plant …) while the queue waits.

**A turn:** optionally play a trick card, then tap a counter. At counters 1–4 the **scene** comes first (decided per
counter and round, the same for everybody; the first contact with a counter is always the appointment question):
- «Do you have an appointment?» – «Yes» only with a 📅 appointment card. «No»: «We are fully booked for the next 9
  months» (in a completely empty waiting room) – then one argument: insist politely, «it's urgent», «only a tiny
  question», 🥐 croissants or 🤝 «my cousin works here». The clerk's mood (grumpy, sleepy, chatty, cheerful) changes
  the chance. If it works, the clerk phones a colleague with a sigh («I have a citizen here who seems to be very
  important …») and you get an audience; if not, come back another day.
- A huge queue (the display does not move while the clerks chat): wait patiently (50 %: it is your turn – else your
  place is kept for your next turn) or try one of three tricks (back from the toilet, «only a signature», delivery
  person, a big official folder, a stroller with a doll, croissants for the queue) – each with its own chance and a
  funny consequence when caught: back to the end of the queue, the queue complains (−1 relation) or the clerk closes
  the counter for the day.
- Nobody there: straight to the audience.

At the audience you hand in a missing document (a stamp) – or an **authority card** of that counter is revealed
(about 40 cards): a stamp, two stamps, a referral («Not responsible – go to counter 4»; the next turn must go there,
ping-pong between counters is counted), a document is needed («Form B-12 in triplicate, blue only», «a certified copy
of the original» – in the folder: a stamp, else it is missing until fetched from the archive), lunch break (miss the
next turn), holiday («so is the substitute»), a grumpy clerk, a trick card, the tree, or a **mini-game**: an absurd
form (tick the boxes before they slide away), stamping yourself at the right moment, bureaucratic speak («according
to article 7, paragraph 3, item pancake …» – which item was it?). The server checks every mini-game (the stamp timing
by its own clock); with mini-games switched off, and for bots, a chance decides.

**Trick cards** (at most 4 in the hand, 2 at the start): 📅 appointment, 🥐 croissants (opens almost every door, and
the clerk's good mood draws two cards – the better one counts), 🤝 connections (a sure way in, or cancel a
referral), 💌 small gift (+2 stamps – but the 🕵️ order inspector catches it with 35 %: a fine stamp −1 and back to
counter 1; the rules say playfully that this is only a joke in the game and that friendliness and patience work much
better in real life), 📎 complete folder (protects once against «something is missing»), 🗣️ stay friendly (the next
grumpy clerk melts: a stamp), ⚖️ objection and 📣 talk to the mayor (+1 stamp, referrals and waiting forgotten – every
team once per game).

**Objections ⚖️** («The pizza oven casts a shadow on our garden gnome», «The slide does not fit the townscape», «The
tree house is far too cheerful» …): the other team defends with an expert report (a document from the folder –
always works), neighbours' signatures (45 % + 15 % per relation) or a compromise (75 %; the project gets a funny
condition, e.g. «We paint the slide beige», printed on the permit). A successful objection costs a stamp.

**Events** at the start of a round (from round 2, 30 %): 📜 new regulation (all documents in the folders are invalid),
💻 system migration (this round the counters give no stamps – «computer says no»), 🎉 open day (all counters open,
no queues, no appointments).

**Mode «The Administration»:** one seat plays the administration – a person (who opens the table, or whoever the
leader picks in the lobby) or a bot («family against the administration»). It plays once per round, last: an
authority card on a builder team (referral, lunch break, new regulation, an absurd form to fill in first, a stamp
revoked) or opens / closes a counter (at most two closed). The builders defend automatically with 🤝 / 🗣️ / 📎. The
administration wins when nobody has the permit after 10 / 15 / 22 rounds (short / normal / long).

**The end:** the building permit certificate with all stamps (office and day) and the condition of a compromise, the
ranking and the **funniest moments** («Leo was sent to counter 4 six times», «Mia heard «fully booked for 9 months»
3 times», …). Who leads can help a team that does not act (☰ › Help the team on turn: its step is done as a bot
would) and end the game. The whole game is in the database – it survives a restart and reconnects.

**Coins for places 1–3:** set by the parents in Games › Beat the Bureaucracy (default 10 / 5 / 2), paid once, only
for a game played to the end at a family table with at least two people of the family – never alone against bots,
never for guests or bots. Everybody of the family gets a history entry (with referrals and the time to the permit:
the special quiz «Family Quest Facts» asks who was sent to another counter most often in one game and who got the
permit the fastest).

### Game corner

Family → **🕹️ Game corner**: small games that run on the device itself (only a duel on two devices goes over
the server; best times stay in this browser), shown when family games are on for the child:

- **Tic-Tac-Toe** – against the app (easy, medium, unbeatable), two players on one device, or on **two devices**:
  invite somebody of the family – the invitation pops up in their app; a tally of the rounds.
- **Sudoku** – 4×4 for beginners, 6×6, 9×9 easy / medium / hard; every puzzle has exactly one solution, wrong
  numbers turn red, best time per level.
- **Patience** – the classic solitaire: sort all cards by suit onto four piles, draw 1 or 3, undo, «Finish» when
  only open cards are left. Tap a card and it moves where it fits.
- **Ping-Pong** – against the app (easy, medium, hard) or face to face on one tablet; first to 7 points. Also on
  **two devices** (a duel) and as **doubles on up to four devices**: two teams of two, each with a paddle at the
  baseline and a short paddle (55 %) near the net that only moves along its line. Whoever opens the table plays the
  back paddle of team A and chooses who sits on the three other seats – a family member (the invitation pops up in
  their app) or a bot (easy, normal, hard) – and the points to win (5, 7 or 11). A seat whose person says «no thanks»
  can be given to somebody else or a bot; the match starts once everybody is ready. Every player moves only their own
  paddle and always sees their own team at the bottom. If somebody leaves, a bot plays on for them; if the host
  leaves, the match ends. Like the duels, doubles pay no coins and are kept in memory only.
- **Pairs** – turn over two cards and find the pairs: animals, fruit, vehicles, sea animals or **your own photo
  sets**; alone (fewest moves), against the app (it remembers more or less well) or 2–4 players on one device.
  Card back: four patterns or the **family crest**.
- **🧊 Cube solver** – helps to bring a mixed-up puzzle cube back to one colour per side. Choose **2×2** or **3×3**
  (4×4 is shown as «coming later»), then paint the colours you see on a **3D cube**: drag it with a finger or the
  mouse, or jump to a side with the six side buttons; pick a colour and tap a sticker. On small phones the flat
  **net** (▦) is easier. The 3×3 centres are fixed – hold the cube with **yellow on top and green in front**. 🧽 clears
  everything, ✨ fills in a solved cube, 🎲 mixes one to try it out. The colours stay in this browser, so a refresh
  loses nothing. **Solve** first checks the colours and says in plain words what is wrong – a colour used too often,
  stickers without colour, «This corner cannot exist: white-yellow-red», two colours of a corner swapped, a piece
  that is there twice (the stickers blink), or «one corner is twisted / one edge is flipped / two pieces are
  swapped» (a cube that cannot be solved like this – usually one sticker is painted wrong). Then a **step-by-step
  guide**: the move in standard notation (U D L R F B, ' = anticlockwise, 2 = twice) plus a sentence and an arrow
  («Turn the RIGHT side up ↑»), the 3D cube turns the layer and shows the result; ◀ Back, Next ▶, 🔁 show again,
  «Step 12 of 110», the next moves, and confetti at the end. The 3×3 is solved **layer by layer** like in the
  beginner's method, in seven phases with a short explanation each (white cross, white corners, middle layer,
  yellow cross, yellow edges, yellow corners to their place, turn the yellow corners) – about 135 moves on average,
  never more than about 200; the cube is never turned as a whole. The 2×2 is solved the **shortest way** (at most
  11 moves); the corner at the back, bottom left never moves. Everything runs on the device (the search in a Web
  Worker); nothing is sent to the server. Parents switch it on or off in Settings › Games like the other games.

- **🎰 One-armed bandit** – a slot machine with three reels: pull the lever for 1 coin, three times a day; three alike
  win (7️⃣ 100, ⭐ 40, 🔔 20, 🍊 10, 🍋 8, 🍒 5 coins), two cherries anywhere 2, one cherry gives the coin back. The
  reels are drawn on the server. It uses the **standard game price**: by default a child buys it once for **250
  coins** or rents it for 20 coins a day (a free try = one spin); the parents can change the price and the rent or set 0 (free). Whoever bought it before (for 150 coins) keeps
  it. **Win chance** (slider 1–10 in its settings, default 5) sets what comes back on average: 5 ≈ 92 % like a typical
  casino machine, 10 ≈ 120 %, 1 ≈ 60 % (straight steps in between; the hint under the slider shows the value). The pay
  table stays; the server draws the outcome first with the win chances of the reels scaled to that return, then shows
  reels that fit it.

**Photo sets** (parent area › Games › 🛠️ Custom games › 🧠 Pair Hunt): upload photos into named sets (every
photo becomes a pair; a set needs at least 3 photos) – used by the Paarjagd and the pairs game. **Family crest**
(parent area › Settings): design the family crest – name, an emoji, two colours and a
pattern (plain, split, quartered, diagonal band, chevron). Photos no set uses any more are deleted when you save.

### Guests

Whoever leads a family quiz or a bingo game can tap **👥 Invite guests**: a QR code appears. Friends or
grandparents scan it with their phone in the home network (direct access must be on), type a name and play along
– nothing else of the app is open to them. Guests are deleted with everything they did after 12 hours. Parents can
switch guests off under Settings → Games.

**Guest networks** (Settings → Access from the network): devices in these address ranges – e.g. your guest
Wi-Fi – can only open the guest page and play with an invitation; no family login, no app, no parent area.

### Pet sitting, pet hotel and the hamster

Away for some days (camp, holidays at the grandparents)? On the pet card, **🧳 Pet sitting**: hand the pet to a family
member until a day – they find it under «Pets in my care» and feed (paying the food), play and wash it; the bars keep
dropping as usual. Or book the **Family Quest pet hotel** for 1–30 days (Settings → «Pet hotel: coins per day», default
10, paid at once): no decay, no death, the pet comes back fed, happy and clean; fetched early, full unused days are paid
back. The **hamster** 🐹 (shop, 300 coins) runs in its wheel while it is healthy (every bar at least 50) and mines coins
for its owner – Settings → «Hamster: coins per day», default 15 (5 more than a day in the pet hotel).

### Pairs game: photos from Home Assistant Media and the crest as a picture

Settings → «Pairs game: photo sets and family crest»: every photo set takes its pictures either **from Home Assistant
Media** (Media → My media, the `/media` folder – the app reads it, nothing is changed there) or as an upload from the
device (iPhone photos in HEIC are turned into JPEG by the browser). Chosen pictures are copied into Family Quest and saved
right away. The **family crest** can be an own picture too (upload or Home Assistant Media); it is shown in the shield,
on the card backs and on the dashboard. After the update that adds the media folder, restart the app once.

### Picture questions: cantons

Quiz templates **«Kantone erkennen (Umrisse)»** (which canton has this shape?) and **«Kantone auf der Karte»**
(which canton is marked?) – outlines from the FSO / swisstopo generalised boundaries – and **«Kantonswappen
erkennen»** (simplified vector drawings of the coats of arms, drawn for Family Quest – `tools/build_arms.py`).
Flags in the flag quizzes are shown as sharp SVG pictures (country-flag-icons, MIT) instead of emoji.

### Estimation and map questions

- **Estimate:** everybody sets a number with a slider or types it (between minimum and maximum, with a unit) –
  e.g. «How high is the Matterhorn?». The closest answer gets 1000 points, the second 500, the third 250.
- **Map:** everybody taps a pin on the map of Switzerland (cantons, lakes) or Europe (countries) – e.g. «Where is
  Berlin?». The distance is measured in km; the closest pin wins the same way. The solution shows all pins.
- Templates: **«Schätzfragen»**, **«Wo liegt das? (Schweiz)»** and **«Wo liegt das? (Europa)»**. In the quiz
  editor every question has a type: multiple choice, estimate a number or place on a map (tap the right place).

### Template collections by region

The templates can be filtered with **Show:** – general, Switzerland, Germany, Austria, the Netherlands (the choice is
remembered on the device). New: *Deutschland: Bundesländer*, *Deutschland allgemein*, *Österreich: Bundesländer*,
*Niederlande: Provinzen*, *Niederlande allgemein*.

## My card box (own flash cards)

Everybody (children and parents) keeps **own decks** – e.g. «French words». On the start page **📇 My card box**
shows how many cards are due.

- **Own cards:** «+ New card» with front and back; «Save and next» for typing many words in a row.
- **From the packs with one click:** in a lesson, after answering, **📇 To my card box** puts the word (or the
  pairs of that task) into the deck of its subject – the deck is made automatically (e.g. «French», «Geography»,
  «General knowledge»). In a pack, **📇** next to a unit adds all its cards. Cards already in the deck are skipped.
- **Repeating:** the Leitner boxes as in the packs – known → one box up, not known → box 1, «almost» → tomorrow
  again. «Repeat» takes the due cards and up to 15 new ones, «Practise all» every card in random order; ⇄ swaps the
  sides (e.g. French → German).
- **What sits and what not:** every card shows its status – ✅ known (box 3 and up), 📈 learning, 🔁 due (should be
  known by now), 🌱 new; the bar and the filter chips show the counts.

Repeating the own cards gives no points (own cards could be made very easy).

## 💡 Code Workshop (block programming)
**Only in Family Quest Dev for now** (`channel.DEV_FEATURES`): in stable and beta the tile, the routes, the parent
section and the API (`/api/codelab/*` → 404) do not exist.

Children learn to program with blocks – made for a phone in portrait. On the **Learning** page a tile «💡 Code Workshop»
opens three parts: **🧩 Puzzles**, **🎨 My programs** and **👨‍👩‍👧 Family programs**. Time in the workshop counts as
**learning time** (the daily learning limit and the learning hours of the child), not as game time: the app sends a
heartbeat every 30 s while it is open (at most 45 s per heartbeat are booked); with the limit used up the workshop does
not open (saving still works).

**The editor:** the stage on top (480 × 360, 0/0 in the middle; ▴ hides it, landscape: stage left, code right), the
sprite tabs (🖼️ Stage for the backdrops, one tab per sprite – tap the open one for its settings: name, costumes, size,
direction, turning style, duplicate, delete – ＋ for a new sprite), the code as a **vertical list**: a script starts with
an event ⚡, blocks inside C blocks (repeat, if) are indented with a coloured bracket. **Tap a gap** (the caret ＋) and
then a **block card** in the drawer below (chips per category) – it is inserted there; after «repeat» the caret goes into
the loop. Values: tap them – a big number pad (directions with arrows), pickers for sprites, costumes, backdrops,
arrows and messages; conditions (◇) get a value block (touching?, = < >, and / or / not, random). **Long press** a block:
a menu (duplicate, switch off, up / down, delete) – keep holding and **drag** it (with everything inside) to another
gap. ↶ ↷ undo / redo; programs save themselves. Stopped, a sprite can be dragged on the stage to its start place.
**▶ Start** (always from the start positions), **⏹**, **🐢 slow motion** (the running block lights up), tap a sprite or
swipe / the arrow pad / the arrow keys for the events.

**Blocks (stage 1):** ⚡ when ▶ Start is pressed, when this sprite is tapped, when arrow ← → ↑ ↓ is pressed, when I receive
✉️ …, send ✉️ … to all · 🏃 move, turn ↻ / ↺, go to x/y, go to (a sprite / random place), glide, point in direction, change
x / y, if on edge bounce · 🎨 say / think for n s, switch costume / backdrop, next costume, change / set size, show / hide ·
🔁 repeat n, repeat forever, if, if-else, wait, wait until, stop everything · ❓ touching (a sprite / the edge)?, random,
= < >, and / or / not (puzzles also «way blocked?»). The engine (web/codelab.js) is our own interpreter – no code of the
child is run as JavaScript: every script is a thread that yields once per frame in loops and waits, at most 100 threads
and 12 sprites, a loop that runs for ever without a pause gets a friendly hint. Sprites: 16 own drawings with 2–3
costumes (`web/img/codelab/`), own sprites and backdrops with the drawing editor; backdrops from the library scenes and
the rooms of the adventure games.

**🧩 Puzzles** (`familyquest/codelab_levels.json`): 15 levels in 3 worlds on a grid – «bring the fox to the star»:
👣 step by step (move, turn), 🔁 loops (only one step per «move», block limits, a loop in a loop, repeat forever), ⚡ events
and if (tap the fox, steer with arrows, «if way blocked? turn else move»). Only the blocks of the level are in the drawer;
⭐⭐⭐ for few blocks, a 💡 hint, 👣 step by step. A stone or the edge ends a try, a loop that runs more than 1000 blocks
too. The server checks a solution again (`codelab.simulate`: the same rules, the taps / arrows given are replayed), keeps
the best ⭐ and the fewest blocks per child and pays **XP / coins once per level** on the first solve (parent setting,
default 10 XP). Levels open one after the other (parents: all).

**🎨 Own programs:** templates «Empty program», «Dancing cat», «Catch the star», «Greeting card». Who sees a program –
like the books: **🔒 only me** (parents neither; in the parent area only that it exists), **🧒 other children**,
**👨‍👩‍👧 whole family** (default). Who may see it plays it; **🔀 Remix** makes an own copy (the card names the original).
Only the author changes a program; parents remove shared ones. The server checks every program (`clean_program`): only
known blocks, every value of its type, at most 12 sprites, 800 blocks, 12 nested levels, 700 KB (own drawings cleaned
like in the books); 60 programs per person, 300 per family. A deleted profile takes its programs along.

**Parent area › Learning packs › 💡 Code Workshop:** on / off per child, the reward for a first solved level, the puzzle
progress per child (levels, ⭐ per world), the shared programs (open in the app, remove) and the private ones only as
«exists».

## Language courses and general knowledge

Learning app › **Language courses & more**: everybody (children and adults) chooses a language and a level and
starts it – German, French, English and Spanish, each in three levels
A1 Beginner, A2 Basics, B1 Advanced, plus **General knowledge** (inventions, buildings, history, science, space, art,
sport … – German questions, so a parent adds it first under «More packs»). The units of a course unlock one after the other; the exercises mix choice, typing, pairs, listening, gap
sentences and flash cards. Courses are not switched on automatically (`standard: false`, `selbst: true` in the pack).

**In every app language:** titles, units and descriptions appear in the app language, and the courses ask in the
learner's language – a French child learning English sees «bonjour → good morning», a Swedish child «god morgon → good
morning» (all 9 app languages; own languages fall back to the family language, the language of the parent area, then
English). A course is never offered in the language it teaches (no French course for French speakers). The learning
progress belongs to the card, not to the text: switching the language keeps it.

**Packs in one language only** (general knowledge, German, Thurgau geography, «5. Klasse Thurgau»): not installed in a
new family. Parent area › Learning packs › **➕ More packs** shows them with their content language («🇩🇪 Content in
German») – **Add** (or **Add all German-language packs**) makes them available, then switch them on per child; for
German-speaking families the section is at the top. **⋯ › Remove from the family** puts a pack back (switched off for
every child, the progress is kept). On updating, nothing a child learnt with is touched: packs nobody has go to «More
packs»; in families whose language is not German, German-only packs that were switched on automatically and never
used are switched off once (when the parent area is opened for the first time after the update).
